from typing import Any


def retrieve(query: str, top_k: int = 5) -> dict[str, Any]:
    return {
        "query": query,
        "top_k": top_k,
        "status": "rag_placeholder",
        "results": [
            {
                "id": "chunk-1",
                "score": 0.92,
                "text": "这里将返回与问题最相关的教材片段。",
            }
        ],
    }
