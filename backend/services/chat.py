from __future__ import annotations

import json
import re
from typing import Any

_chat_history: dict[str, list[dict]] = {}


def extract_keywords(message: str) -> list[str]:
    """提取知识点名称（简单版：提取引号内容或常见名词）"""
    quoted = re.findall(r'[「『"\'](.*?)[」』"\']', message)
    if quoted:
        return quoted

    words = re.findall(r'[一-龥]{2,10}', message)
    return words[:3]


def detect_intent_by_rules(message: str) -> dict | None:
    """规则匹配（快速路径）"""
    msg = message.lower()
    keywords = extract_keywords(message)

    if "保留" in msg or "不要删" in msg or "不要合并" in msg:
        return {"intent": "keep", "keywords": keywords, "confidence": 0.9}

    if "合并" in msg or "整合" in msg:
        return {"intent": "merge", "keywords": keywords, "confidence": 0.85}

    if "拆分" in msg or "分开" in msg or "分离" in msg:
        return {"intent": "split", "keywords": keywords, "confidence": 0.9}

    if "为什么" in msg or "原因" in msg or "解释" in msg:
        return {"intent": "explain", "keywords": keywords, "confidence": 0.95}

    return None


INTENT_LLM_PROMPT = """你是一位意图识别助手。
用户输入一句话，你需要判断用户的意图。

【可能的意图】
- keep: 用户希望保留某个知识点，不要删除或合并
- merge: 用户希望合并两个知识点
- split: 用户希望拆分已合并的知识点
- explain: 用户询问为什么做了某个决策
- unknown: 无法识别意图

【输入】
{message}

【输出】
只输出一个 JSON 对象：
{{
  "intent": "keep/merge/split/explain/unknown",
  "keywords": ["知识点名称1", "知识点名称2"],
  "confidence": 0.0~1.0
}}
"""


def detect_intent(message: str) -> dict:
    """意图识别主流程"""
    result = detect_intent_by_rules(message)
    if result:
        return result

    from .llm import get_active_provider

    try:
        provider = get_active_provider()
        resp = provider.chat(
            "你是意图识别助手，只输出 JSON。",
            INTENT_LLM_PROMPT.format(message=message),
            temperature=0.1,
            response_format_json=True
        )
        return json.loads(resp.content)
    except Exception:
        return {"intent": "unknown", "keywords": [], "confidence": 0.0}


def execute_keep(keywords: list[str], merge_id: str) -> dict:
    """保留操作：找到匹配的节点，将其决策改为 keep。"""
    from . import graph_store

    merge_result = graph_store.load_merged_graph(merge_id)
    if not merge_result:
        return {"success": False, "message": "未找到整合结果"}

    decisions = merge_result.get("decisions", [])
    if isinstance(decisions, str):
        decisions = json.loads(decisions)

    matched = []
    for kw in keywords:
        for dec in decisions:
            if dec["type"] in ("remove", "merge"):
                node_name = ""
                if "merged_node" in dec:
                    node_name = dec["merged_node"].get("name", "")
                elif "node" in dec:
                    node_name = dec["node"] if isinstance(dec["node"], str) else dec["node"].get("name", "")

                if kw in node_name:
                    matched.append(dec)

    if not matched:
        return {"success": False, "message": f"未找到匹配的知识点：{keywords}"}

    for dec in matched:
        dec["type"] = "keep"
        dec["reason"] = "教师要求保留（对话修改）"
        dec["confidence"] = 1.0

    updated_graph = merge_result.get("graph", {})

    graph_store.save_merged_graph(
        merge_id,
        merge_result["textbook_ids"],
        updated_graph,
        decisions,
        status=merge_result["status"],
        provider=merge_result.get("provider"),
        model=merge_result.get("model"),
        original_nodes=merge_result["original_nodes"],
        original_chars=merge_result.get("original_chars", 0)
    )

    return {
        "success": True,
        "message": f"已将 {len(matched)} 个知识点标记为保留",
        "updated_decisions": decisions,
        "updated_graph": updated_graph
    }


def execute_split(keywords: list[str], merge_id: str) -> dict:
    """拆分操作：找到 merge 决策，拆分为多个 keep。"""
    from . import graph_store

    merge_result = graph_store.load_merged_graph(merge_id)
    if not merge_result:
        return {"success": False, "message": "未找到整合结果"}

    decisions = merge_result.get("decisions", [])
    if isinstance(decisions, str):
        decisions = json.loads(decisions)

    matched = []
    for kw in keywords:
        for dec in decisions:
            if dec["type"] == "merge":
                node_name = dec.get("merged_node", {}).get("name", "")
                if kw in node_name:
                    matched.append(dec)

    if not matched:
        return {"success": False, "message": f"未找到匹配的合并决策：{keywords}"}

    for dec in matched:
        dec["type"] = "keep"
        dec["reason"] = "教师要求拆分（对话修改）"

    updated_graph = merge_result.get("graph", {})

    graph_store.save_merged_graph(
        merge_id,
        merge_result["textbook_ids"],
        updated_graph,
        decisions,
        status=merge_result["status"],
        provider=merge_result.get("provider"),
        model=merge_result.get("model"),
        original_nodes=merge_result["original_nodes"],
        original_chars=merge_result.get("original_chars", 0)
    )

    return {
        "success": True,
        "message": f"已拆分 {len(matched)} 个合并决策",
        "updated_decisions": decisions,
        "updated_graph": updated_graph
    }


def execute_explain(keywords: list[str], merge_id: str) -> dict:
    """解释操作：找到匹配的决策，返回其 reason。"""
    from . import graph_store

    merge_result = graph_store.load_merged_graph(merge_id)
    if not merge_result:
        return {"success": False, "message": "未找到整合结果"}

    decisions = merge_result.get("decisions", [])
    if isinstance(decisions, str):
        decisions = json.loads(decisions)

    matched = []
    for kw in keywords:
        for dec in decisions:
            node_name = ""
            if "merged_node" in dec:
                node_name = dec["merged_node"].get("name", "")
            elif "node" in dec:
                node_name = dec["node"] if isinstance(dec["node"], str) else dec["node"].get("name", "")

            if kw in node_name:
                matched.append(dec)

    if not matched:
        return {"success": False, "message": f"未找到匹配的决策：{keywords}"}

    explanations = []
    for dec in matched:
        node_name = dec.get("merged_node", {}).get("name") or dec.get("node", "未知")
        reason = dec.get("reason", "无理由")
        confidence = dec.get("confidence", 0.0)
        explanations.append(f"- **{node_name}**（{dec['type']}）：{reason}（置信度 {confidence:.2f}）")

    return {
        "success": True,
        "message": "以下是相关决策的解释：\n\n" + "\n".join(explanations),
        "updated_decisions": decisions,
        "updated_graph": merge_result.get("graph", {})
    }


def chat_with_teacher(message: str, merge_id: str, session_id: str = "default") -> dict[str, Any]:
    """教师对话主流程。"""
    intent_result = detect_intent(message)
    intent = intent_result["intent"]
    keywords = intent_result["keywords"]

    if intent == "keep":
        result = execute_keep(keywords, merge_id)
    elif intent == "split":
        result = execute_split(keywords, merge_id)
    elif intent == "explain":
        result = execute_explain(keywords, merge_id)
    elif intent == "merge":
        result = {"success": False, "message": "合并操作较复杂，建议重新运行整合功能。"}
    else:
        result = {"success": False, "message": "抱歉，我没有理解您的意图。请尝试：\n- 保留某个知识点\n- 拆分某个合并\n- 询问为什么做了某个决策"}

    if session_id not in _chat_history:
        _chat_history[session_id] = []
    _chat_history[session_id].append({"role": "user", "content": message})
    _chat_history[session_id].append({"role": "assistant", "content": result["message"]})

    return {
        "reply": result["message"],
        "success": result["success"],
        "updated_decisions": result.get("updated_decisions", []),
        "updated_graph": result.get("updated_graph", {})
    }


def get_chat_history(session_id: str = "default") -> list[dict]:
    """获取对话历史"""
    return _chat_history.get(session_id, [])


def reply(message: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """兼容旧接口"""
    return {
        "status": "deprecated",
        "message": "请使用 /api/chat/message 接口",
    }
