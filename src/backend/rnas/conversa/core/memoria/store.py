from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from core.models import Example


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS examples (
            example_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_text TEXT NOT NULL,
            assistant_text TEXT NOT NULL,
            added_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_examples_added_at ON examples(added_at);
        """
    )
    conn.commit()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_example(conn: sqlite3.Connection, user_text: str, assistant_text: str) -> Example:
    u = (user_text or "").strip()
    a = (assistant_text or "").strip()
    if not u or not a:
        raise ValueError("user_text e assistant_text são obrigatórios.")

    conn.execute(
        "INSERT INTO examples(user_text, assistant_text, added_at) VALUES(?, ?, ?)",
        (u, a, utc_now_iso()),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM examples ORDER BY example_id DESC LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("Falha ao inserir exemplo.")
    return _row_to_example(row)


def list_recent(conn: sqlite3.Connection, limit: int = 50) -> list[Example]:
    rows = conn.execute(
        "SELECT * FROM examples ORDER BY example_id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [_row_to_example(r) for r in rows]


def iter_all(conn: sqlite3.Connection) -> Iterable[Example]:
    rows = conn.execute("SELECT * FROM examples ORDER BY example_id ASC").fetchall()
    for r in rows:
        yield _row_to_example(r)


def count_examples(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM examples").fetchone()
    return int(row[0]) if row else 0


def _row_to_example(row) -> Example:
    return Example(
        example_id=int(row["example_id"]),
        user_text=str(row["user_text"]),
        assistant_text=str(row["assistant_text"]),
        added_at=datetime.fromisoformat(str(row["added_at"])),
    )
