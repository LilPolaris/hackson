from typing import Any


def reply(message: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "status": "chat_placeholder",
        "message": message,
        "history_length": len(history or []),
        "answer": "这是教师反馈智能体的占位回复，后续会接入真实模型与上下文。",
    }
