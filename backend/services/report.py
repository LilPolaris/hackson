from typing import Any


def generate_report(topic: str, textbook_ids: list[str]) -> dict[str, Any]:
    return {
        "status": "report_placeholder",
        "topic": topic,
        "textbook_ids": textbook_ids,
        "outline": [
            "教材来源",
            "知识点整合策略",
            "重复与互补分析",
            "压缩后的精华内容",
            "教师反馈与迭代记录",
        ],
    }
