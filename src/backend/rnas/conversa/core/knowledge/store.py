from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from core.models import KnowledgeChunk


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            text TEXT NOT NULL,
            meta_json TEXT NOT NULL DEFAULT '',
            added_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_added_at ON knowledge_chunks(added_at);
        CREATE INDEX IF NOT EXISTS idx_knowledge_source ON knowledge_chunks(source);
        """
    )
    conn.commit()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_chunk(conn: sqlite3.Connection, source: str, text: str, meta_json: str = "") -> KnowledgeChunk:
    src = (source or "").strip()
    tx = (text or "").strip()
    if not src or not tx:
        raise ValueError("source e text sao obrigatorios.")

    conn.execute(
        "INSERT INTO knowledge_chunks(source, text, meta_json, added_at) VALUES(?, ?, ?, ?)",
        (src, tx, meta_json or "", utc_now_iso()),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM knowledge_chunks ORDER BY chunk_id DESC LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("Falha ao inserir chunk.")
    return _row_to_chunk(row)


def iter_chunks(conn: sqlite3.Connection) -> Iterable[KnowledgeChunk]:
    rows = conn.execute("SELECT * FROM knowledge_chunks ORDER BY chunk_id ASC").fetchall()
    for r in rows:
        yield _row_to_chunk(r)


def count_chunks(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM knowledge_chunks").fetchone()
    return int(row[0]) if row else 0


def _row_to_chunk(row) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=int(row["chunk_id"]),
        source=str(row["source"]),
        text=str(row["text"]),
        meta_json=str(row["meta_json"] or ""),
        added_at=datetime.fromisoformat(str(row["added_at"])),
    )
