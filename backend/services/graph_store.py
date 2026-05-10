import sqlite3
from contextlib import contextmanager
import json
from pathlib import Path
from typing import Any

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "graph.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS graphs (
    textbook_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    built_at TEXT NOT NULL,
    source_textbook TEXT
);

CREATE TABLE IF NOT EXISTS nodes (
    id TEXT NOT NULL,
    textbook_id TEXT NOT NULL,
    name TEXT NOT NULL,
    definition TEXT,
    category TEXT,
    chapter TEXT,
    page INTEGER,
    source_textbook TEXT,
    PRIMARY KEY (textbook_id, id),
    FOREIGN KEY (textbook_id) REFERENCES graphs(textbook_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_nodes_textbook ON nodes(textbook_id);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    textbook_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    description TEXT,
    FOREIGN KEY (textbook_id) REFERENCES graphs(textbook_id) ON DELETE CASCADE,
    FOREIGN KEY (textbook_id, source_id) REFERENCES nodes(textbook_id, id) ON DELETE CASCADE,
    FOREIGN KEY (textbook_id, target_id) REFERENCES nodes(textbook_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_edges_textbook ON edges(textbook_id);

CREATE TABLE IF NOT EXISTS merged_graphs (
    merge_id TEXT PRIMARY KEY,
    textbook_ids TEXT NOT NULL,
    status TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    merged_at TEXT NOT NULL,
    original_nodes INTEGER,
    merged_nodes INTEGER,
    original_chars INTEGER,
    merged_chars INTEGER,
    compression_ratio REAL,
    decisions TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS merged_nodes (
    id TEXT PRIMARY KEY,
    merge_id TEXT NOT NULL,
    name TEXT NOT NULL,
    definition TEXT,
    category TEXT,
    source_nodes TEXT,
    FOREIGN KEY (merge_id) REFERENCES merged_graphs(merge_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_merged_nodes_merge ON merged_nodes(merge_id);

CREATE TABLE IF NOT EXISTS merged_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merge_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    description TEXT,
    FOREIGN KEY (merge_id) REFERENCES merged_graphs(merge_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_merged_edges_merge ON merged_edges(merge_id);
"""


@contextmanager
def _conn():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


def save_graph(
    textbook_id: str,
    graph: dict[str, Any],
    *,
    status: str,
    provider: str | None,
    model: str | None,
    source_textbook: str | None,
) -> None:
    from datetime import datetime, timezone

    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute("DELETE FROM edges WHERE textbook_id = ?", (textbook_id,))
        c.execute("DELETE FROM nodes WHERE textbook_id = ?", (textbook_id,))
        c.execute("DELETE FROM graphs WHERE textbook_id = ?", (textbook_id,))
        c.execute(
            "INSERT INTO graphs(textbook_id,status,provider,model,built_at,source_textbook) "
            "VALUES (?,?,?,?,?,?)",
            (textbook_id, status, provider, model, now, source_textbook),
        )
        for node in graph["nodes"]:
            c.execute(
                "INSERT INTO nodes(id,textbook_id,name,definition,category,chapter,page,source_textbook) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    node["id"],
                    textbook_id,
                    node["name"],
                    node.get("definition"),
                    node.get("category"),
                    node.get("chapter"),
                    node.get("page"),
                    node.get("source_textbook"),
                ),
            )
        for edge in graph["edges"]:
            c.execute(
                "INSERT INTO edges(textbook_id,source_id,target_id,relation_type,description) "
                "VALUES (?,?,?,?,?)",
                (
                    textbook_id,
                    edge["source"],
                    edge["target"],
                    edge["relation_type"],
                    edge.get("description"),
                ),
            )


def load_graph(textbook_id: str) -> dict[str, Any] | None:
    init_db()
    with _conn() as c:
        head = c.execute("SELECT * FROM graphs WHERE textbook_id = ?", (textbook_id,)).fetchone()
        if not head:
            return None

        nodes = [
            dict(row)
            for row in c.execute(
                "SELECT id,name,definition,category,chapter,page,source_textbook "
                "FROM nodes WHERE textbook_id = ? ORDER BY id",
                (textbook_id,),
            )
        ]
        edge_rows = c.execute(
            "SELECT source_id,target_id,relation_type,description "
            "FROM edges WHERE textbook_id = ? ORDER BY id",
            (textbook_id,),
        )
        edges = [
            {
                "source": row["source_id"],
                "target": row["target_id"],
                "relation_type": row["relation_type"],
                "description": row["description"],
            }
            for row in edge_rows
        ]
        return {
            "textbook_id": textbook_id,
            "status": head["status"],
            "provider": head["provider"],
            "model": head["model"],
            "built_at": head["built_at"],
            "source_textbook": head["source_textbook"],
            "graph": {"nodes": nodes, "edges": edges},
        }


def delete_graph(textbook_id: str) -> dict[str, int]:
    """Delete one textbook's single-book graph and stale merged results that include it."""
    init_db()
    with _conn() as c:
        edge_count = c.execute("SELECT COUNT(*) FROM edges WHERE textbook_id = ?", (textbook_id,)).fetchone()[0]
        node_count = c.execute("SELECT COUNT(*) FROM nodes WHERE textbook_id = ?", (textbook_id,)).fetchone()[0]
        graph_count = c.execute("SELECT COUNT(*) FROM graphs WHERE textbook_id = ?", (textbook_id,)).fetchone()[0]

        c.execute("DELETE FROM edges WHERE textbook_id = ?", (textbook_id,))
        c.execute("DELETE FROM nodes WHERE textbook_id = ?", (textbook_id,))
        c.execute("DELETE FROM graphs WHERE textbook_id = ?", (textbook_id,))

        merge_ids: list[str] = []
        for row in c.execute("SELECT merge_id,textbook_ids FROM merged_graphs"):
            try:
                ids = json.loads(row["textbook_ids"])
            except json.JSONDecodeError:
                ids = []
            if textbook_id in ids:
                merge_ids.append(row["merge_id"])

        for merge_id in merge_ids:
            c.execute("DELETE FROM merged_edges WHERE merge_id = ?", (merge_id,))
            c.execute("DELETE FROM merged_nodes WHERE merge_id = ?", (merge_id,))
            c.execute("DELETE FROM merged_graphs WHERE merge_id = ?", (merge_id,))

        return {
            "graphs": graph_count,
            "nodes": node_count,
            "edges": edge_count,
            "merged_graphs": len(merge_ids),
        }


def save_merged_graph(
    merge_id: str,
    textbook_ids: list[str],
    graph: dict[str, Any],
    decisions: list[dict[str, Any]],
    *,
    status: str,
    provider: str | None,
    model: str | None,
    original_nodes: int,
    original_chars: int,
) -> None:
    """Save a cross-textbook merge result and its audit decisions."""
    from datetime import datetime, timezone

    init_db()
    now = datetime.now(timezone.utc).isoformat()
    merged_nodes_count = len(graph.get("nodes", []))
    merged_chars = sum(len(node.get("definition") or "") for node in graph.get("nodes", []))
    compression_ratio = merged_chars / original_chars if original_chars > 0 else 0.0

    with _conn() as c:
        c.execute("DELETE FROM merged_edges WHERE merge_id = ?", (merge_id,))
        c.execute("DELETE FROM merged_nodes WHERE merge_id = ?", (merge_id,))
        c.execute("DELETE FROM merged_graphs WHERE merge_id = ?", (merge_id,))
        c.execute(
            "INSERT INTO merged_graphs(merge_id,textbook_ids,status,provider,model,merged_at,"
            "original_nodes,merged_nodes,original_chars,merged_chars,compression_ratio,decisions) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                merge_id,
                json.dumps(textbook_ids, ensure_ascii=False),
                status,
                provider,
                model,
                now,
                original_nodes,
                merged_nodes_count,
                original_chars,
                merged_chars,
                compression_ratio,
                json.dumps(decisions, ensure_ascii=False),
            ),
        )
        for node in graph.get("nodes", []):
            c.execute(
                "INSERT INTO merged_nodes(id,merge_id,name,definition,category,source_nodes) "
                "VALUES (?,?,?,?,?,?)",
                (
                    node["id"],
                    merge_id,
                    node["name"],
                    node.get("definition"),
                    node.get("category"),
                    json.dumps(node.get("source_nodes", []), ensure_ascii=False),
                ),
            )
        for edge in graph.get("edges", []):
            c.execute(
                "INSERT INTO merged_edges(merge_id,source_id,target_id,relation_type,description) "
                "VALUES (?,?,?,?,?)",
                (
                    merge_id,
                    edge["source"],
                    edge["target"],
                    edge["relation_type"],
                    edge.get("description"),
                ),
            )


def load_merged_graph(merge_id: str) -> dict[str, Any] | None:
    """Load a saved cross-textbook merge result."""
    init_db()
    with _conn() as c:
        head = c.execute("SELECT * FROM merged_graphs WHERE merge_id = ?", (merge_id,)).fetchone()
        if not head:
            return None

        nodes = [
            dict(row)
            for row in c.execute(
                "SELECT id,name,definition,category,source_nodes "
                "FROM merged_nodes WHERE merge_id = ? ORDER BY id",
                (merge_id,),
            )
        ]
        for node in nodes:
            try:
                node["source_nodes"] = json.loads(node.get("source_nodes") or "[]")
            except json.JSONDecodeError:
                node["source_nodes"] = []

        edge_rows = c.execute(
            "SELECT source_id,target_id,relation_type,description "
            "FROM merged_edges WHERE merge_id = ? ORDER BY id",
            (merge_id,),
        )
        edges = [
            {
                "source": row["source_id"],
                "target": row["target_id"],
                "relation_type": row["relation_type"],
                "description": row["description"],
            }
            for row in edge_rows
        ]

        return {
            "merge_id": merge_id,
            "textbook_ids": json.loads(head["textbook_ids"]),
            "status": head["status"],
            "provider": head["provider"],
            "model": head["model"],
            "merged_at": head["merged_at"],
            "original_nodes": head["original_nodes"],
            "merged_nodes": head["merged_nodes"],
            "original_chars": head["original_chars"],
            "merged_chars": head["merged_chars"],
            "compression_ratio": head["compression_ratio"],
            "decisions": json.loads(head["decisions"]),
            "graph": {"nodes": nodes, "edges": edges},
        }
