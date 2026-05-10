import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import graph_store
from .llm import get_active_provider
from .llm.base import BaseLLMProvider

_PARSED_DIR = Path(__file__).resolve().parent.parent / "data" / "parsed"
_RELATION_TYPES = {"prerequisite", "parallel", "contains", "applies_to"}
_BUILD_STATUS: dict[str, dict[str, Any]] = {}
_BUILD_STATUS_LOCK = threading.Lock()
_DEFAULT_MAX_CHAPTERS = 24

SYSTEM_PROMPT = """你是一位教材知识点抽取专家。
你的任务：从给定的一章教材正文中，抽取知识点节点和节点之间的关系，用于构建知识图谱。

【硬性约束】
1. 只输出一个 JSON 对象，不要输出任何解释性文字，不要输出 Markdown 代码块围栏。
2. JSON 必须严格符合下方 schema。
3. 所有字段的中文文本要简洁、学术、规范，禁止出现“本章”“上一节”等指代性措辞。
4. 关系类型只能从以下四个枚举值中选：
   - prerequisite：A 是学习 B 的先修知识（A→B）
   - parallel：A 与 B 属于同层级、并列概念
   - contains：A 是一个更大的概念，包含 B
   - applies_to：A 是一个概念/原理，B 是它的应用场景或实例
5. 节点 id 使用 "node_001" 这样的三位零填充序号，章内唯一。
6. 边的 source/target 必须引用本次输出的 node id，不得凭空引用。

【输出 JSON schema】
{
  "nodes": [
    {
      "id": "node_001",
      "name": "知识点中文名（≤20字）",
      "definition": "一句话定义（≤80字）",
      "category": "核心概念 | 子概念 | 性质 | 应用 中的一个",
      "chapter": "第X章 章节标题（直接填入给定的章节标题）",
      "page": 整数,
      "source_textbook": "教材标题（直接填入给定值）"
    }
  ],
  "edges": [
    {
      "source": "node_001",
      "target": "node_002",
      "relation_type": "prerequisite",
      "description": "一句话解释两者关系（≤40字）"
    }
  ]
}

【质量要求】
- 每章抽取的核心概念数量控制在 5~15 个，不要过多也不要过少。
- 边的数量通常为节点数的 1~2 倍。
- 优先抽取“会出现在考试/作业中的”概念，而不是引言性的泛化描述。
"""

USER_PROMPT_TEMPLATE = """【教材标题】{source_textbook}
【章节标题】{chapter_title}
【起始页码】{page_start}

【章节正文】
{content}

请按 system prompt 要求输出 JSON。"""


def _truncate_chapter_content(content: str, max_chars: int = 8000) -> str:
    """Keep long chapters within a predictable prompt budget."""
    if len(content) <= max_chars:
        return content
    head = content[: max_chars // 2]
    tail = content[-max_chars // 2 :]
    return f"{head}\n\n……（中间省略 {len(content) - max_chars} 字）……\n\n{tail}"


def _extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from strict JSON or a fenced/annotated model response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("LLM 未返回合法 JSON")


def _extract_from_chapter(
    provider: BaseLLMProvider,
    source_textbook: str,
    chapter: dict[str, Any],
    id_offset: int,
) -> dict[str, Any]:
    chapter_title = chapter.get("title", "")
    page_start = chapter.get("page_start", 1)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        source_textbook=source_textbook,
        chapter_title=chapter_title,
        page_start=page_start,
        content=_truncate_chapter_content(chapter.get("content", "")),
    )
    resp = provider.chat(SYSTEM_PROMPT, user_prompt, temperature=0.2, response_format_json=True)
    data = _extract_json(resp.content)

    old2new: dict[str, str] = {}
    renamed_nodes = []
    for idx, node in enumerate(data.get("nodes", []), start=1):
        old_id = node.get("id")
        if not old_id or not node.get("name"):
            continue
        new_id = f"node_{id_offset + idx:03d}"
        old2new[old_id] = new_id
        renamed_nodes.append(
            {
                "id": new_id,
                "name": str(node.get("name", ""))[:40],
                "definition": node.get("definition", ""),
                "category": node.get("category") or "核心概念",
                "chapter": node.get("chapter") or chapter_title,
                "page": node.get("page") or page_start,
                "source_textbook": node.get("source_textbook") or source_textbook,
            }
        )

    renamed_edges = []
    for edge in data.get("edges", []):
        source = old2new.get(edge.get("source"))
        target = old2new.get(edge.get("target"))
        relation_type = edge.get("relation_type")
        if not source or not target or relation_type not in _RELATION_TYPES:
            continue
        renamed_edges.append(
            {
                "source": source,
                "target": target,
                "relation_type": relation_type,
                "description": edge.get("description", ""),
            }
        )

    return {"nodes": renamed_nodes, "edges": renamed_edges}


def _mock_graph(source_textbook: str) -> dict[str, Any]:
    """Fallback graph used only when real extraction cannot run."""
    nodes = [
        {
            "id": "node_001",
            "name": "核心概念A",
            "definition": "章节的核心理论基础。",
            "category": "核心概念",
            "chapter": "第一章",
            "page": 1,
            "source_textbook": source_textbook,
        },
        {
            "id": "node_002",
            "name": "子概念B",
            "definition": "核心概念A的具体展开。",
            "category": "子概念",
            "chapter": "第一章",
            "page": 3,
            "source_textbook": source_textbook,
        },
        {
            "id": "node_003",
            "name": "性质C",
            "definition": "子概念B的关键性质。",
            "category": "性质",
            "chapter": "第一章",
            "page": 5,
            "source_textbook": source_textbook,
        },
        {
            "id": "node_004",
            "name": "应用D",
            "definition": "核心概念A的典型应用场景。",
            "category": "应用",
            "chapter": "第一章",
            "page": 8,
            "source_textbook": source_textbook,
        },
        {
            "id": "node_005",
            "name": "扩展E",
            "definition": "性质C推广得到的结论。",
            "category": "核心概念",
            "chapter": "第二章",
            "page": 12,
            "source_textbook": source_textbook,
        },
    ]
    edges = [
        {"source": "node_001", "target": "node_002", "relation_type": "contains", "description": "A包含B"},
        {
            "source": "node_002",
            "target": "node_003",
            "relation_type": "prerequisite",
            "description": "先学B才能理解C",
        },
        {"source": "node_001", "target": "node_004", "relation_type": "applies_to", "description": "A应用于D"},
        {
            "source": "node_003",
            "target": "node_005",
            "relation_type": "prerequisite",
            "description": "C是E的先修",
        },
    ]
    return {"nodes": nodes, "edges": edges}


def _load_parsed(textbook_id: str) -> dict[str, Any] | None:
    parsed_file = _PARSED_DIR / f"{textbook_id}.json"
    if not parsed_file.exists():
        return None
    return json.loads(parsed_file.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chapter_limit() -> int:
    raw = os.getenv("GRAPH_BUILD_MAX_CHAPTERS", str(_DEFAULT_MAX_CHAPTERS)).strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_MAX_CHAPTERS


def _set_build_status(textbook_id: str, **patch: Any) -> dict[str, Any]:
    now = _utc_now()
    with _BUILD_STATUS_LOCK:
        current = {
            "textbook_id": textbook_id,
            "status": "idle",
            "current": 0,
            "total": 0,
            "message": "等待构建",
            **_BUILD_STATUS.get(textbook_id, {}),
        }
        if patch.get("status") == "running" and current.get("status") != "running":
            patch.setdefault("started_at", now)
        updated = {**current, **patch, "updated_at": now}
        _BUILD_STATUS[textbook_id] = updated
        return dict(updated)


def get_build_status(textbook_id: str) -> dict[str, Any]:
    with _BUILD_STATUS_LOCK:
        status = _BUILD_STATUS.get(textbook_id)
        if status:
            return dict(status)

    cached = graph_store.load_graph(textbook_id)
    if cached is not None:
        is_built = cached.get("status") == "built"
        return {
            "textbook_id": textbook_id,
            "status": cached.get("status") or "empty",
            "current": 1,
            "total": 1,
            "message": "图谱已构建" if is_built else "已生成演示图谱",
            "provider": cached.get("provider"),
            "model": cached.get("model"),
            "built_at": cached.get("built_at"),
        }

    parsed = _load_parsed(textbook_id)
    chapter_count = len(parsed.get("chapters", [])) if parsed else 0
    return {
        "textbook_id": textbook_id,
        "status": "parsed" if chapter_count else "idle",
        "current": 0,
        "total": chapter_count,
        "message": "已解析，等待构建" if chapter_count else "等待解析",
    }


def _save_mock(textbook_id: str, source_textbook: str, error: str) -> dict[str, Any]:
    graph = _mock_graph(source_textbook)
    graph_store.save_graph(
        textbook_id,
        graph,
        status="mock",
        provider=None,
        model=None,
        source_textbook=source_textbook,
    )
    _set_build_status(
        textbook_id,
        status="mock",
        message="LLM 调用失败，已生成演示图谱",
        error=error,
        provider=None,
        model=None,
    )
    return {
        "textbook_id": textbook_id,
        "status": "mock",
        "provider": None,
        "model": None,
        "error": error,
        "graph": graph,
    }


def build_graph(payload: dict[str, Any]) -> dict[str, Any]:
    textbook_id = payload.get("textbook_id", "demo-textbook")
    parsed = _load_parsed(textbook_id)
    source_textbook = (parsed or {}).get("title") or textbook_id

    if not parsed or not parsed.get("chapters"):
        _set_build_status(
            textbook_id,
            status="mock",
            current=0,
            total=0,
            message="未找到解析结果，已生成演示图谱",
            error="parsed JSON not found",
        )
        return _save_mock(textbook_id, source_textbook, "parsed JSON not found")

    chapters = [chapter for chapter in parsed.get("chapters", []) if (chapter.get("content") or "").strip()]
    full_total = len(chapters)
    if full_total == 0:
        _set_build_status(
            textbook_id,
            status="mock",
            current=0,
            total=0,
            message="解析结果没有可抽取正文，已生成演示图谱",
            error="parsed chapters are empty",
        )
        return _save_mock(textbook_id, source_textbook, "parsed chapters are empty")

    limit = _chapter_limit()
    selected_chapters = chapters[:limit] if limit and full_total > limit else chapters
    selected_total = len(selected_chapters)
    is_limited = selected_total < full_total
    _set_build_status(
        textbook_id,
        status="running",
        current=0,
        total=selected_total,
        total_chapters=full_total,
        limit=limit or None,
        limited=is_limited,
        message=f"准备抽取知识点：0/{selected_total}",
        error=None,
    )

    try:
        provider = get_active_provider()
        all_nodes: list[dict[str, Any]] = []
        all_edges: list[dict[str, Any]] = []
        id_offset = 0
        for index, chapter in enumerate(selected_chapters, start=1):
            chapter_title = chapter.get("title") or f"片段 {index}"
            _set_build_status(
                textbook_id,
                status="running",
                current=index - 1,
                total=selected_total,
                message=f"正在抽取 {index}/{selected_total}：{chapter_title}",
                provider=provider.key,
                model=getattr(provider, "model", None),
            )
            sub_graph = _extract_from_chapter(provider, source_textbook, chapter, id_offset)
            all_nodes.extend(sub_graph["nodes"])
            all_edges.extend(sub_graph["edges"])
            id_offset += len(sub_graph["nodes"])
            _set_build_status(
                textbook_id,
                status="running",
                current=index,
                total=selected_total,
                message=f"已完成 {index}/{selected_total}：{chapter_title}",
                node_count=len(all_nodes),
                edge_count=len(all_edges),
            )

        if not all_nodes:
            raise ValueError("LLM 未抽取到任何节点")

        graph = {"nodes": all_nodes, "edges": all_edges}
        model = getattr(provider, "model", None)
        graph_store.save_graph(
            textbook_id,
            graph,
            status="built",
            provider=provider.key,
            model=model,
            source_textbook=source_textbook,
        )
        _set_build_status(
            textbook_id,
            status="built",
            current=selected_total,
            total=selected_total,
            total_chapters=full_total,
            limit=limit or None,
            limited=is_limited,
            message="图谱已构建" if not is_limited else f"已按上限处理 {selected_total}/{full_total} 个片段",
            node_count=len(all_nodes),
            edge_count=len(all_edges),
            provider=provider.key,
            model=model,
            error=None,
        )
        return {
            "textbook_id": textbook_id,
            "status": "built",
            "provider": provider.key,
            "model": model,
            "error": None,
            "processed_chapters": selected_total,
            "total_chapters": full_total,
            "limited": is_limited,
            "graph": graph,
        }
    except Exception as exc:
        _set_build_status(
            textbook_id,
            status="mock",
            current=0,
            total=selected_total,
            total_chapters=full_total,
            limit=limit or None,
            limited=is_limited,
            message="LLM 调用失败，已生成演示图谱",
            error=str(exc),
        )
        return _save_mock(textbook_id, source_textbook, str(exc))


def get_graph(textbook_id: str) -> dict[str, Any]:
    cached = graph_store.load_graph(textbook_id)
    if cached is None:
        return {
            "textbook_id": textbook_id,
            "status": "empty",
            "provider": None,
            "model": None,
            "error": None,
            "graph": {"nodes": [], "edges": []},
        }
    return {
        "textbook_id": cached["textbook_id"],
        "status": cached["status"],
        "provider": cached["provider"],
        "model": cached["model"],
        "built_at": cached["built_at"],
        "error": None,
        "graph": cached["graph"],
    }
