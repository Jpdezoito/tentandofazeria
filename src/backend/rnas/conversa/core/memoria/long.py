from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from core.nlp.normalize import tokenize


@dataclass(frozen=True)
class LongMemoryItem:
    memory_id: int
    key: str
    value: str
    tags: str
    added_at: datetime


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS long_memory (
            memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '',
            added_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_long_memory_added_at ON long_memory(added_at);
        CREATE INDEX IF NOT EXISTS idx_long_memory_key ON long_memory(key);
        """
    )
    conn.commit()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_fact(conn: sqlite3.Connection, key: str, value: str, tags: str = "") -> LongMemoryItem:
    k = (key or "").strip()
    v = (value or "").strip()
    if not k or not v:
        raise ValueError("key e value sao obrigatorios.")
    conn.execute(
        "INSERT INTO long_memory(key, value, tags, added_at) VALUES(?, ?, ?, ?)",
        (k, v, tags or "", utc_now_iso()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM long_memory ORDER BY memory_id DESC LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("Falha ao inserir memoria.")
    return _row_to_item(row)


def iter_all(conn: sqlite3.Connection) -> Iterable[LongMemoryItem]:
    rows = conn.execute("SELECT * FROM long_memory ORDER BY memory_id ASC").fetchall()
    for r in rows:
        yield _row_to_item(r)


def search_facts(conn: sqlite3.Connection, query: str, limit: int = 5) -> list[LongMemoryItem]:
    q = (query or "").strip()
    if not q:
        return []
    tokens = set(tokenize(q))
    if not tokens:
        return []

    scored: list[tuple[float, LongMemoryItem]] = []
    for item in iter_all(conn):
        text = f"{item.key} {item.value} {item.tags}"
        toks = set(tokenize(text))
        if not toks:
            continue
        inter = len(tokens & toks)
        union = len(tokens | toks)
        score = float(inter / union) if union else 0.0
        if score <= 0.0:
            continue
        scored.append((score, item))

    scored.sort(key=lambda it: it[0], reverse=True)
    return [s[1] for s in scored[: max(1, int(limit))]]


def _row_to_item(row) -> LongMemoryItem:
    return LongMemoryItem(
        memory_id=int(row["memory_id"]),
        key=str(row["key"]),
        value=str(row["value"]),
        tags=str(row["tags"] or ""),
        added_at=datetime.fromisoformat(str(row["added_at"])),
    )
