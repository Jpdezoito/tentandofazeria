from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class DbItemRow:
    path: str
    display_name: str
    name_norm: str
    kind: str
    source: str
    mtime: float
    size: int
    ext: str


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
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS items (
            path TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            name_norm TEXT NOT NULL,
            kind TEXT NOT NULL,
            source TEXT NOT NULL,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            ext TEXT NOT NULL,
            scan_id INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_items_name_norm ON items(name_norm);
        CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
        CREATE INDEX IF NOT EXISTS idx_items_ext ON items(ext);

        CREATE TABLE IF NOT EXISTS scans (
            scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at REAL NOT NULL,
            root TEXT NOT NULL
        );
        """
    )
    conn.commit()


def begin_scan(conn: sqlite3.Connection, root: str, started_at: float) -> int:
    cur = conn.execute("INSERT INTO scans(started_at, root) VALUES(?, ?)", (started_at, root))
    conn.commit()
    return int(cur.lastrowid)


def upsert_items(conn: sqlite3.Connection, rows: Iterable[DbItemRow], scan_id: int) -> None:
    conn.executemany(
        """
        INSERT INTO items(path, display_name, name_norm, kind, source, mtime, size, ext, scan_id)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            display_name=excluded.display_name,
            name_norm=excluded.name_norm,
            kind=excluded.kind,
            source=excluded.source,
            mtime=excluded.mtime,
            size=excluded.size,
            ext=excluded.ext,
            scan_id=excluded.scan_id
        """,
        (
            (r.path, r.display_name, r.name_norm, r.kind, r.source, r.mtime, r.size, r.ext, scan_id)
            for r in rows
        ),
    )


def touch_scan_ids(conn: sqlite3.Connection, paths: Iterable[str], scan_id: int) -> None:
    """Update only the scan_id for already-indexed paths."""

    conn.executemany("UPDATE items SET scan_id=? WHERE path=?", ((scan_id, p) for p in paths))


def get_existing_mtime_size(conn: sqlite3.Connection, paths: list[str]) -> dict[str, tuple[float, int]]:
    """Return existing (mtime, size) for given paths."""

    if not paths:
        return {}

    placeholders = ",".join("?" for _ in paths)
    cur = conn.execute(
        f"SELECT path, mtime, size FROM items WHERE path IN ({placeholders})",
        paths,
    )
    out: dict[str, tuple[float, int]] = {}
    for row in cur.fetchall():
        out[str(row["path"])] = (float(row["mtime"]), int(row["size"]))
    return out


def finalize_scan(conn: sqlite3.Connection, source: str, scan_id: int) -> None:
    # Drop items that were not seen in this scan for this source.
    conn.execute("DELETE FROM items WHERE source=? AND scan_id<>?", (source, scan_id))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (f"last_scan_id:{source}", str(scan_id)))
    conn.commit()


def item_count(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT COUNT(*) AS c FROM items")
    return int(cur.fetchone()["c"])


def query_candidates(
    conn: sqlite3.Connection,
    token: str,
    limit: int,
    ext_filter: Optional[str] = None,
) -> list[sqlite3.Row]:
    token_like = f"%{token}%"
    if ext_filter:
        cur = conn.execute(
            """
            SELECT path, display_name, name_norm, kind, source, mtime, size, ext
            FROM items
            WHERE (name_norm LIKE ? OR display_name LIKE ?) AND ext=?
            LIMIT ?
            """,
            (token_like, token_like, ext_filter.lower(), limit),
        )
    else:
        cur = conn.execute(
            """
            SELECT path, display_name, name_norm, kind, source, mtime, size, ext
            FROM items
            WHERE (name_norm LIKE ? OR display_name LIKE ?)
            LIMIT ?
            """,
            (token_like, token_like, limit),
        )
    return list(cur.fetchall())


def get_item_by_path(conn: sqlite3.Connection, path: str) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT path, display_name, name_norm, kind, source, mtime, size, ext
        FROM items
        WHERE path=?
        """,
        (path,),
    )
    row = cur.fetchone()
    return row if row is not None else None
