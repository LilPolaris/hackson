from __future__ import annotations

import hashlib
import json
import re
import uuid
from difflib import SequenceMatcher
from typing import Any

_EMBEDDING_MODEL: Any = None
_EMBEDDING_CACHE: dict[str, Any] = {}
_EMBEDDING_FAILED_REASON: str | None = None
_RELATION_TYPES = {"prerequisite", "parallel", "contains", "applies_to"}
_TARGET_COMPRESSION_RATIO = 0.32
_MIN_COMPRESSION_RATIO = 0.25
_MAX_COMPRESSION_RATIO = 0.40

MERGE_REASON_PROMPT = """你是一位教材整合专家。
给定两个来自不同教材的知识点，判断它们是否应该合并。

【知识点 A】
- 名称：{name_a}
- 定义：{def_a}
- 来源：{source_a}，{chapter_a}

【知识点 B】
- 名称：{name_b}
- 定义：{def_b}
- 来源：{source_b}，{chapter_b}

【任务】
输出一个 JSON 对象：
{{
  "should_merge": true/false,
  "reason": "一句话解释（≤50字）",
  "confidence": 0.0~1.0,
  "merged_name": "合并后的统一名称（如果 should_merge=true）",
  "merged_definition": "合并后的定义（如果 should_merge=true，综合两者，≤100字）"
}}

【约束】
1. 只输出 JSON，不要其他文字。
2. should_merge=true 的条件：两者描述的是同一个概念，只是表述不同。
3. should_merge=false 的条件：两者是不同概念，或者一个是另一个的子集/应用。
4. confidence 反映你的判断把握程度。
"""


def merge_textbooks(textbook_ids: list[str]) -> dict[str, Any]:
    """Legacy endpoint wrapper."""
    return merge_textbooks_v2(textbook_ids)


def merge_textbooks_v2(textbook_ids: list[str]) -> dict[str, Any]:
    """
    Merge multiple textbook knowledge graphs into one compressed graph.

    The normal path uses embedding-based candidate discovery plus LLM decisions.
    If embeddings or LLM calls are unavailable, the whole run falls back to a
    deterministic rule-based mock merge so the API still returns useful output.
    """
    from . import graph_store

    merge_id = str(uuid.uuid4())
    all_nodes: list[dict[str, Any]] = []
    all_edges: list[dict[str, Any]] = []
    original_chars = 0

    for textbook_id in textbook_ids:
        loaded = graph_store.load_graph(textbook_id)
        if not loaded:
            continue
        graph = loaded.get("graph", {})
        source_textbook = loaded.get("source_textbook") or textbook_id
        for node in graph.get("nodes", []):
            enriched = dict(node)
            enriched["_textbook_id"] = textbook_id
            enriched["_source_key"] = _source_key(enriched)
            enriched["source_textbook"] = enriched.get("source_textbook") or source_textbook
            all_nodes.append(enriched)
            original_chars += len(enriched.get("definition") or "")
        for edge in graph.get("edges", []):
            enriched_edge = dict(edge)
            enriched_edge["_textbook_id"] = textbook_id
            all_edges.append(enriched_edge)

    if not all_nodes:
        return {"merge_id": merge_id, "status": "empty", "error": "No graphs found"}

    original_nodes_count = len(all_nodes)

    try:
        if get_embedding_model() == "failed":
            raise RuntimeError(f"embedding model unavailable: {_EMBEDDING_FAILED_REASON}")

        attempts: list[tuple[float, list[dict[str, Any]], dict[str, Any], float]] = []
        for threshold in (0.75, 0.65, 0.85):
            merge_groups = find_merge_groups(all_nodes, threshold=threshold)
            decisions = generate_decisions(merge_groups, all_nodes)
            merged_graph = apply_decisions(decisions, all_nodes, all_edges)
            ratio = _compression_ratio(merged_graph, original_chars)
            attempts.append((threshold, decisions, merged_graph, ratio))
            if _MIN_COMPRESSION_RATIO <= ratio <= _MAX_COMPRESSION_RATIO:
                break
            if ratio < _MIN_COMPRESSION_RATIO:
                # Higher threshold preserves more nodes when the graph became too small.
                continue

        threshold, decisions, merged_graph, compression_ratio = min(
            attempts,
            key=lambda item: abs(item[3] - _TARGET_COMPRESSION_RATIO),
        )
        if compression_ratio > _MAX_COMPRESSION_RATIO:
            merged_graph = _compress_graph_definitions(merged_graph, original_chars)
            compression_ratio = _compression_ratio(merged_graph, original_chars)
            decisions.append(
                {
                    "action": "compress",
                    "threshold": threshold,
                    "reason": "整合后字数仍偏高，按目标压缩比压缩节点定义。",
                    "confidence": 0.8,
                }
            )

        from .llm import get_active_provider

        provider = get_active_provider()
        graph_store.save_merged_graph(
            merge_id,
            textbook_ids,
            merged_graph,
            decisions,
            status="merged",
            provider=provider.key,
            model=getattr(provider, "model", None),
            original_nodes=original_nodes_count,
            original_chars=original_chars,
        )
        return {
            "merge_id": merge_id,
            "status": "merged",
            "provider": provider.key,
            "model": getattr(provider, "model", None),
            "original_nodes": original_nodes_count,
            "merged_nodes": len(merged_graph["nodes"]),
            "original_chars": original_chars,
            "merged_chars": sum(len(node.get("definition") or "") for node in merged_graph["nodes"]),
            "compression_ratio": compression_ratio,
            "decisions": decisions,
            "graph": merged_graph,
        }
    except Exception as exc:
        mock_graph, mock_decisions = generate_mock_merge(all_nodes, all_edges)
        mock_graph = _compress_graph_definitions(mock_graph, original_chars)
        compression_ratio = _compression_ratio(mock_graph, original_chars)
        graph_store.save_merged_graph(
            merge_id,
            textbook_ids,
            mock_graph,
            mock_decisions,
            status="mock",
            provider=None,
            model=None,
            original_nodes=original_nodes_count,
            original_chars=original_chars,
        )
        return {
            "merge_id": merge_id,
            "status": "mock",
            "error": str(exc),
            "original_nodes": original_nodes_count,
            "merged_nodes": len(mock_graph["nodes"]),
            "original_chars": original_chars,
            "merged_chars": sum(len(node.get("definition") or "") for node in mock_graph["nodes"]),
            "compression_ratio": compression_ratio,
            "decisions": mock_decisions,
            "graph": mock_graph,
        }


def get_embedding_model() -> Any:
    global _EMBEDDING_FAILED_REASON, _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL
    try:
        from sentence_transformers import SentenceTransformer

        try:
            _EMBEDDING_MODEL = SentenceTransformer(
                "paraphrase-multilingual-MiniLM-L12-v2",
                local_files_only=True,
            )
        except TypeError:
            _EMBEDDING_MODEL = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    except Exception as exc:
        _EMBEDDING_FAILED_REASON = str(exc)
        _EMBEDDING_MODEL = "failed"
    return _EMBEDDING_MODEL


def name_similarity(name1: str, name2: str) -> float:
    return SequenceMatcher(None, name1 or "", name2 or "").ratio()


def semantic_similarity(def1: str, def2: str) -> float:
    global _EMBEDDING_FAILED_REASON, _EMBEDDING_MODEL
    if not def1 or not def2:
        return 0.0

    model = get_embedding_model()
    if model == "failed":
        return 0.0

    try:
        import numpy as np

        emb1 = _encode_definition(model, def1)
        emb2 = _encode_definition(model, def2)
        denom = float(np.linalg.norm(emb1) * np.linalg.norm(emb2))
        if denom == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / denom)
    except Exception as exc:
        _EMBEDDING_FAILED_REASON = str(exc)
        _EMBEDDING_MODEL = "failed"
        return 0.0


def chapter_similarity(ch1: str, ch2: str) -> float:
    return SequenceMatcher(None, ch1 or "", ch2 or "").ratio()


def category_match(cat1: str, cat2: str) -> float:
    if not cat1 or not cat2:
        return 0.5
    return 1.0 if cat1 == cat2 else 0.5


def definition_length_similarity(def1: str, def2: str) -> float:
    len1 = len(def1 or "")
    len2 = len(def2 or "")
    if len1 == 0 and len2 == 0:
        return 1.0
    return min(len1, len2) / max(len1, len2, 1)


def merge_score(node1: dict[str, Any], node2: dict[str, Any]) -> float:
    """
    Score whether two nodes describe the same concept.

    Design: name similarity is the cheap coarse gate; semantic similarity carries
    the most weight; chapter/category/definition-length are stabilizers that
    reduce false positives across unrelated contexts.
    """
    s1 = name_similarity(node1.get("name", ""), node2.get("name", ""))
    s2 = semantic_similarity(node1.get("definition", ""), node2.get("definition", ""))
    s3 = chapter_similarity(node1.get("chapter", ""), node2.get("chapter", ""))
    s4 = category_match(node1.get("category", ""), node2.get("category", ""))
    s5 = definition_length_similarity(node1.get("definition", ""), node2.get("definition", ""))
    return 0.22 * s1 + 0.45 * s2 + 0.12 * s3 + 0.11 * s4 + 0.10 * s5


def find_merge_groups(nodes: list[dict[str, Any]], threshold: float) -> list[list[dict[str, Any]]]:
    """Find transitive cross-textbook node groups whose merge score passes threshold."""
    parent = {_source_key(node): _source_key(node) for node in nodes}
    by_key = {_source_key(node): node for node in nodes}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for idx, node_a in enumerate(nodes):
        for node_b in nodes[idx + 1 :]:
            if node_a.get("_textbook_id") == node_b.get("_textbook_id"):
                continue
            if name_similarity(node_a.get("name", ""), node_b.get("name", "")) < 0.7:
                continue
            if merge_score(node_a, node_b) >= threshold:
                union(_source_key(node_a), _source_key(node_b))

    grouped: dict[str, list[dict[str, Any]]] = {}
    for key, node in by_key.items():
        grouped.setdefault(find(key), []).append(node)
    return [
        sorted(group, key=_source_key)
        for group in grouped.values()
        if len(group) > 1
    ]


def generate_decisions(
    merge_groups: list[list[dict[str, Any]]],
    all_nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate merge/keep/remove decisions, using the LLM for each candidate group."""
    decisions: list[dict[str, Any]] = []
    consumed: set[str] = set()

    for group in sorted(merge_groups, key=lambda item: _source_key(item[0])):
        candidates = [node for node in group if _source_key(node) not in consumed]
        if len(candidates) < 2:
            continue

        representative = _best_representative(candidates)
        accepted = [representative]
        positive_results: list[dict[str, Any]] = []

        for node in candidates:
            if _source_key(node) == _source_key(representative):
                continue
            result = ask_llm_merge_decision(representative, node)
            if result.get("should_merge"):
                accepted.append(node)
                positive_results.append(result)
            else:
                key = _source_key(node)
                decisions.append(
                    {
                        "action": "keep",
                        "node": key,
                        "reason": result.get("reason") or "LLM 判断为互补或不同概念。",
                        "confidence": _clamp_float(result.get("confidence"), 0.0, 1.0),
                    }
                )
                consumed.add(key)

        if len(accepted) >= 2:
            merge_result = max(
                positive_results,
                key=lambda item: _clamp_float(item.get("confidence"), 0.0, 1.0),
            )
            source_keys = [_source_key(node) for node in accepted]
            confidence = _clamp_float(merge_result.get("confidence"), 0.0, 1.0)
            merged_node = _make_merged_node(
                accepted,
                merged_name=merge_result.get("merged_name"),
                merged_definition=merge_result.get("merged_definition"),
            )
            decisions.append(
                {
                    "action": "merge",
                    "nodes": source_keys,
                    "merged_node": merged_node,
                    "reason": merge_result.get("reason") or "多个教材描述同一知识点，合并保留综合定义。",
                    "confidence": confidence,
                }
            )
            for redundant_key in source_keys[1:]:
                decisions.append(
                    {
                        "action": "remove",
                        "node": redundant_key,
                        "reason": f"已并入 {merged_node['name']}。",
                        "confidence": confidence,
                    }
                )
            consumed.update(source_keys)
        else:
            key = _source_key(representative)
            if key not in consumed:
                decisions.append(
                    {
                        "action": "keep",
                        "node": key,
                        "reason": "未找到可确认合并的跨教材重复知识点。",
                        "confidence": 0.75,
                    }
                )
                consumed.add(key)

    for node in sorted(all_nodes, key=_source_key):
        key = _source_key(node)
        if key not in consumed:
            decisions.append(
                {
                    "action": "keep",
                    "node": key,
                    "reason": "未发现高置信度重复，作为互补知识点保留。",
                    "confidence": 0.88,
                }
            )
            consumed.add(key)

    return decisions


def ask_llm_merge_decision(node_a: dict[str, Any], node_b: dict[str, Any]) -> dict[str, Any]:
    from .llm import get_active_provider

    user_prompt = MERGE_REASON_PROMPT.format(
        name_a=node_a.get("name", ""),
        def_a=node_a.get("definition", ""),
        source_a=node_a.get("source_textbook", ""),
        chapter_a=node_a.get("chapter", ""),
        name_b=node_b.get("name", ""),
        def_b=node_b.get("definition", ""),
        source_b=node_b.get("source_textbook", ""),
        chapter_b=node_b.get("chapter", ""),
    )
    provider = get_active_provider()
    resp = provider.chat(
        "你是教材整合专家，只输出 JSON。",
        user_prompt,
        temperature=0.2,
        response_format_json=True,
        timeout=45.0,
    )
    data = _extract_json(resp.content)
    if not isinstance(data.get("should_merge"), bool):
        raise ValueError("LLM merge decision missing should_merge")
    data["confidence"] = _clamp_float(data.get("confidence"), 0.0, 1.0)
    return data


def apply_decisions(
    decisions: list[dict[str, Any]],
    all_nodes: list[dict[str, Any]],
    all_edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the merged graph and reconnect edges through the source-node mapping."""
    node_by_key = {_source_key(node): node for node in all_nodes}
    source_to_merged: dict[str, str | None] = {}
    merged_nodes: list[dict[str, Any]] = []
    run_prefix = uuid.uuid4().hex[:8]

    def add_node(node: dict[str, Any], source_keys: list[str]) -> str:
        new_id = f"merged_{run_prefix}_{len(merged_nodes) + 1:03d}"
        public = {
            "id": new_id,
            "name": node.get("name") or "未命名知识点",
            "definition": node.get("definition") or "",
            "category": node.get("category") or "核心概念",
            "source_nodes": source_keys,
        }
        merged_nodes.append(public)
        return new_id

    for decision in decisions:
        action = decision.get("action")
        if action == "merge":
            source_keys = [key for key in decision.get("nodes", []) if key in node_by_key]
            if not source_keys:
                continue
            merged_node = dict(decision.get("merged_node") or {})
            new_id = add_node(merged_node, source_keys)
            for key in source_keys:
                source_to_merged[key] = new_id
        elif action == "keep":
            key = decision.get("node")
            if key not in node_by_key or key in source_to_merged:
                continue
            source = node_by_key[key]
            new_id = add_node(source, [key])
            source_to_merged[key] = new_id
        elif action == "remove":
            key = decision.get("node")
            if key in node_by_key and key not in source_to_merged:
                source_to_merged[key] = None

    for key, node in sorted(node_by_key.items()):
        if key not in source_to_merged:
            new_id = add_node(node, [key])
            source_to_merged[key] = new_id

    deduped_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for edge in all_edges:
        textbook_id = edge.get("_textbook_id")
        source_key = f"{textbook_id}:{edge.get('source')}"
        target_key = f"{textbook_id}:{edge.get('target')}"
        source_id = source_to_merged.get(source_key)
        target_id = source_to_merged.get(target_key)
        relation_type = edge.get("relation_type")
        if not source_id or not target_id or source_id == target_id or relation_type not in _RELATION_TYPES:
            continue
        edge_key = (source_id, target_id, relation_type)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        deduped_edges.append(
            {
                "source": source_id,
                "target": target_id,
                "relation_type": relation_type,
                "description": edge.get("description") or "",
            }
        )

    return {"nodes": merged_nodes, "edges": deduped_edges}


def generate_mock_merge(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rule-based fallback: merge exact or near-identical names and keep the rest."""
    decisions: list[dict[str, Any]] = []
    consumed: set[str] = set()
    groups = _find_rule_merge_groups(nodes)

    for group in groups:
        available = [node for node in group if _source_key(node) not in consumed]
        if len(available) < 2:
            continue
        source_keys = [_source_key(node) for node in available]
        merged_node = _make_merged_node(available)
        decisions.append(
            {
                "action": "merge",
                "nodes": source_keys,
                "merged_node": merged_node,
                "reason": "Mock fallback：名称完全相同或高度相似，按规则合并。",
                "confidence": 0.72,
            }
        )
        for redundant_key in source_keys[1:]:
            decisions.append(
                {
                    "action": "remove",
                    "node": redundant_key,
                    "reason": f"Mock fallback：已并入 {merged_node['name']}。",
                    "confidence": 0.72,
                }
            )
        consumed.update(source_keys)

    for node in sorted(nodes, key=_source_key):
        key = _source_key(node)
        if key not in consumed:
            decisions.append(
                {
                    "action": "keep",
                    "node": key,
                    "reason": "Mock fallback：未命中名称相同或高度相似规则，保留为互补知识点。",
                    "confidence": 0.7,
                }
            )
            consumed.add(key)

    return apply_decisions(decisions, nodes, edges), decisions


def _encode_definition(model: Any, text: str) -> Any:
    key = hashlib.sha1(text.encode("utf-8")).hexdigest()
    if key not in _EMBEDDING_CACHE:
        _EMBEDDING_CACHE[key] = model.encode(text, convert_to_numpy=True)
    return _EMBEDDING_CACHE[key]


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
    raise ValueError("LLM 未返回合法 JSON")


def _source_key(node: dict[str, Any]) -> str:
    if node.get("_source_key"):
        return str(node["_source_key"])
    textbook_id = node.get("_textbook_id") or node.get("source_textbook") or "unknown"
    return f"{textbook_id}:{node.get('id')}"


def _best_representative(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return max(nodes, key=lambda node: (len(node.get("definition") or ""), len(node.get("name") or "")))


def _make_merged_node(
    nodes: list[dict[str, Any]],
    *,
    merged_name: str | None = None,
    merged_definition: str | None = None,
) -> dict[str, Any]:
    source_keys = [_source_key(node) for node in nodes]
    name = (merged_name or "").strip() or _most_common_value(nodes, "name") or nodes[0].get("name") or "合并知识点"
    definition = (merged_definition or "").strip() or _merge_definitions(nodes)
    category = _most_common_value(nodes, "category") or "核心概念"
    return {
        "name": name[:60],
        "definition": definition[:100],
        "category": category,
        "source_nodes": source_keys,
    }


def _merge_definitions(nodes: list[dict[str, Any]]) -> str:
    definitions: list[str] = []
    for node in sorted(nodes, key=lambda item: len(item.get("definition") or ""), reverse=True):
        definition = (node.get("definition") or "").strip()
        if definition and definition not in definitions:
            definitions.append(definition)
    if not definitions:
        return ""
    merged = "；".join(definitions)
    return merged[:100]


def _most_common_value(nodes: list[dict[str, Any]], field: str) -> str:
    counts: dict[str, int] = {}
    for node in nodes:
        value = str(node.get(field) or "").strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], len(item[0]), item[0]))[0][0]


def _find_rule_merge_groups(nodes: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    parent = {_source_key(node): _source_key(node) for node in nodes}
    by_key = {_source_key(node): node for node in nodes}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for idx, node_a in enumerate(nodes):
        for node_b in nodes[idx + 1 :]:
            if node_a.get("_textbook_id") == node_b.get("_textbook_id"):
                continue
            similarity = name_similarity(node_a.get("name", ""), node_b.get("name", ""))
            if node_a.get("name") == node_b.get("name") or similarity > 0.9:
                union(_source_key(node_a), _source_key(node_b))

    grouped: dict[str, list[dict[str, Any]]] = {}
    for key, node in by_key.items():
        grouped.setdefault(find(key), []).append(node)
    return [
        sorted(group, key=_source_key)
        for group in grouped.values()
        if len(group) > 1
    ]


def _compression_ratio(graph: dict[str, Any], original_chars: int) -> float:
    if original_chars <= 0:
        return 0.0
    merged_chars = sum(len(node.get("definition") or "") for node in graph.get("nodes", []))
    return merged_chars / original_chars


def _compress_graph_definitions(graph: dict[str, Any], original_chars: int) -> dict[str, Any]:
    """Keep the graph structure while shrinking definitions toward the target ratio."""
    if original_chars <= 0 or _compression_ratio(graph, original_chars) <= _MAX_COMPRESSION_RATIO:
        return graph

    target_chars = max(1, int(original_chars * _TARGET_COMPRESSION_RATIO))
    current_chars = sum(len(node.get("definition") or "") for node in graph.get("nodes", []))
    if current_chars <= target_chars:
        return graph

    scale = target_chars / max(current_chars, 1)
    compressed_nodes = []
    for node in graph.get("nodes", []):
        copied = dict(node)
        definition = copied.get("definition") or ""
        budget = max(1, int(len(definition) * scale))
        copied["definition"] = _truncate_text(definition, budget)
        compressed_nodes.append(copied)
    return {"nodes": compressed_nodes, "edges": list(graph.get("edges", []))}


def _truncate_text(text: str, budget: int) -> str:
    if len(text) <= budget:
        return text
    if budget <= 3:
        return text[:budget]
    return text[: budget - 3].rstrip() + "..."


def _clamp_float(value: Any, lower: float, upper: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = lower
    return max(lower, min(upper, number))
