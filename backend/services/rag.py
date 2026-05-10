from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import faiss
    import numpy as np
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

_INDEX_DIR = Path(__file__).resolve().parent.parent / "data" / "rag_index"
_INDEX_DIR.mkdir(parents=True, exist_ok=True)

_EMBEDDING_MODEL: Any = None
_EMBEDDING_FAILED: bool = False


def _get_embedding_model():
    """懒加载 embedding 模型，失败时标记为 failed"""
    global _EMBEDDING_MODEL, _EMBEDDING_FAILED

    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL

    if _EMBEDDING_FAILED:
        return None

    try:
        from sentence_transformers import SentenceTransformer
        _EMBEDDING_MODEL = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        print("✅ Embedding 模型加载成功")
        return _EMBEDDING_MODEL
    except Exception as e:
        print(f"⚠️ Embedding 模型加载失败: {e}")
        _EMBEDDING_FAILED = True
        return None


def chunk_textbook(parsed_data: dict, chunk_size: int = 600, overlap: int = 80) -> list[dict]:
    """
    将教材正文切块。

    参数：
    - chunk_size: 每块约 600 字（中文字符）
    - overlap: 块之间重叠 80 字
    """
    chunks = []
    for ch in parsed_data.get("chapters", []):
        content = ch.get("content", "")
        chapter_title = ch.get("title", "")
        page_start = ch.get("page_start", 1)
        chapter_id = ch.get("chapter_id", "unknown")

        start = 0
        idx = 0
        while start < len(content):
            end = start + chunk_size
            chunk_text = content[start:end]
            estimated_page = page_start + (start // 500)

            chunks.append({
                "chunk_id": f"{parsed_data['textbook_id']}_{chapter_id}_{idx:03d}",
                "textbook_id": parsed_data["textbook_id"],
                "textbook_title": parsed_data.get("title", ""),
                "chapter": chapter_title,
                "page": estimated_page,
                "content": chunk_text.strip(),
            })
            start += chunk_size - overlap
            idx += 1

    return chunks


def build_index(textbook_ids: list[str]) -> dict[str, Any]:
    """
    为指定教材构建 RAG 索引。

    返回：
    {
      "status": "indexed",
      "total_chunks": 1234,
      "textbook_ids": ["生理学A", "生理学B"]
    }
    """
    parsed_dir = Path(__file__).resolve().parent.parent / "data" / "parsed"

    all_chunks = []
    for tid in textbook_ids:
        parsed_file = parsed_dir / f"{tid}.json"
        if parsed_file.exists():
            parsed = json.loads(parsed_file.read_text(encoding="utf-8"))
            all_chunks.extend(chunk_textbook(parsed))

    if not all_chunks:
        return {"status": "empty", "total_chunks": 0, "error": "No parsed textbooks found"}

    # 保存 chunks（无论是否有 embedding）
    chunks_path = _INDEX_DIR / "chunks.json"
    chunks_path.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")

    # 尝试生成 embeddings
    if not FAISS_AVAILABLE:
        return {
            "status": "indexed_without_embeddings",
            "total_chunks": len(all_chunks),
            "textbook_ids": textbook_ids,
            "warning": "FAISS 未安装，将使用关键词匹配"
        }

    model = _get_embedding_model()
    if model is None:
        return {
            "status": "indexed_without_embeddings",
            "total_chunks": len(all_chunks),
            "textbook_ids": textbook_ids,
            "warning": "Embedding 模型加载失败，将使用关键词匹配"
        }

    texts = [c["content"] for c in all_chunks]
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)

    # 构建 FAISS 索引
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # 内积（余弦相似度需要归一化）
    faiss.normalize_L2(embeddings)
    index.add(embeddings)

    # 保存（使用 serialize 绕过 FAISS 在 Windows 上对中文路径的 bug）
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    index_path = _INDEX_DIR / "faiss.index"
    index_bytes = faiss.serialize_index(index)
    index_path.write_bytes(bytes(index_bytes))

    return {
        "status": "indexed",
        "total_chunks": len(all_chunks),
        "textbook_ids": textbook_ids
    }


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """
    检索最相关的 top_k 个 chunk。

    返回：
    [
      {
        "chunk_id": "...",
        "textbook_title": "...",
        "chapter": "...",
        "page": 5,
        "content": "...",
        "score": 0.87
      },
      ...
    ]
    """
    index_path = _INDEX_DIR / "faiss.index"
    chunks_path = _INDEX_DIR / "chunks.json"

    if not chunks_path.exists():
        return []

    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))

    # 如果没有 FAISS 索引，降级到关键词匹配
    if not index_path.exists() or not FAISS_AVAILABLE:
        return _keyword_fallback_retrieve(query, chunks, top_k)

    model = _get_embedding_model()
    if model is None:
        return _keyword_fallback_retrieve(query, chunks, top_k)

    # 正常的向量检索（使用 deserialize 绕过中文路径问题）
    index_bytes = index_path.read_bytes()
    index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype=np.uint8))
    query_emb = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(query_emb)

    scores, indices = index.search(query_emb, min(top_k, len(chunks)))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < len(chunks):
            results.append({**chunks[idx], "score": float(score)})

    return results


def _keyword_fallback_retrieve(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Fallback: 关键词匹配（当 embedding 模型不可用时）"""
    query_lower = query.lower()
    scored_chunks = []

    for chunk in chunks:
        content_lower = chunk["content"].lower()
        # 简单计分：查询词在内容中出现的次数
        score = sum(content_lower.count(word) for word in query_lower.split())
        if score > 0:
            scored_chunks.append({**chunk, "score": float(score)})

    # 按分数排序
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks[:top_k]


def get_rag_status() -> dict[str, Any]:
    """获取 RAG 索引状态"""
    chunks_path = _INDEX_DIR / "chunks.json"
    index_path = _INDEX_DIR / "faiss.index"

    if not chunks_path.exists():
        return {"status": "not_indexed", "total_chunks": 0}

    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    textbook_ids = list(set(c["textbook_id"] for c in chunks))

    has_index = index_path.exists() and FAISS_AVAILABLE

    return {
        "status": "indexed" if has_index else "indexed_without_embeddings",
        "total_chunks": len(chunks),
        "textbook_ids": textbook_ids,
        "has_vector_index": has_index
    }


# LLM 回答生成
RAG_SYSTEM_PROMPT = """你是一位教材知识问答助手。
你的任务：根据给定的教材片段，回答用户的问题。

【硬性约束】
1. 只基于给定的上下文回答，不要编造信息。
2. 每个答案必须标注引用来源，格式：[来源：《教材名》第X章，P.Y]
3. 如果上下文中没有相关信息，回答："当前知识库中未找到相关信息。"
4. 回答要简洁、准确、学术化，不要啰嗦。
5. 如果多个片段都相关，综合回答并分别标注来源。
"""

RAG_USER_PROMPT_TEMPLATE = """【用户问题】
{query}

【相关教材片段】
{context}

请回答用户问题，并标注引用来源。"""


def format_context(chunks: list[dict]) -> str:
    """将检索到的 chunks 格式化为上下文"""
    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(f"[片段 {i}] 《{c['textbook_title']}》{c['chapter']}，P.{c['page']}")
        lines.append(c["content"])
        lines.append("")
    return "\n".join(lines)


def query_rag(query: str, top_k: int = 5) -> dict[str, Any]:
    """
    RAG 问答主流程。

    返回：
    {
      "query": "...",
      "answer": "...[来源：...]",
      "sources": [...]
    }
    """
    chunks = retrieve(query, top_k)

    if not chunks:
        return {
            "query": query,
            "answer": "当前知识库中未找到相关信息。请先上传教材并构建索引。",
            "sources": []
        }

    context = format_context(chunks)
    user_prompt = RAG_USER_PROMPT_TEMPLATE.format(query=query, context=context)

    from .llm import get_active_provider
    try:
        provider = get_active_provider()
        resp = provider.chat(RAG_SYSTEM_PROMPT, user_prompt, temperature=0.3, response_format_json=False)
        answer = resp.content
    except Exception as e:
        # Fallback: LLM 调用失败，直接返回检索到的片段
        answer = f"⚠️ LLM 调用失败：{e}\n\n以下是检索到的相关片段，请自行参考：\n\n"
        for i, c in enumerate(chunks, 1):
            answer += f"[片段 {i}] 《{c['textbook_title']}》{c['chapter']}，P.{c['page']}\n{c['content'][:200]}...\n\n"

    return {
        "query": query,
        "answer": answer,
        "sources": chunks
    }
