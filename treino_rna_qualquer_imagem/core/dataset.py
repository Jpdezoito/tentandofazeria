from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.models import ClusterSummary, ImageRecord


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
        CREATE TABLE IF NOT EXISTS images (
            image_id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            added_at TEXT NOT NULL,
            label TEXT NULL,
            cluster_id TEXT NULL,
            embedding_key TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_images_label ON images(label);
        CREATE INDEX IF NOT EXISTS idx_images_cluster ON images(cluster_id);

        CREATE TABLE IF NOT EXISTS clusters (
            cluster_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            name TEXT NULL
        );
        """
    )
    conn.commit()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_image(
    conn: sqlite3.Connection,
    path: Path,
    embedding_key: str,
    label: Optional[str] = None,
    cluster_id: Optional[str] = None,
) -> ImageRecord:
    p = str(path.resolve())
    conn.execute(
        "INSERT OR IGNORE INTO images(path, added_at, label, cluster_id, embedding_key) VALUES(?, ?, ?, ?, ?)",
        (p, utc_now_iso(), label, cluster_id, embedding_key),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM images WHERE path=?", (p,)).fetchone()
    if row is None:
        raise RuntimeError("Falha ao inserir imagem.")

    return _row_to_image(row)


def set_label(conn: sqlite3.Connection, image_id: int, label: Optional[str]) -> None:
    conn.execute("UPDATE images SET label=?, cluster_id=NULL WHERE image_id=?", (label, image_id))
    conn.commit()


def set_cluster(conn: sqlite3.Connection, image_id: int, cluster_id: Optional[str]) -> None:
    conn.execute("UPDATE images SET cluster_id=?, label=NULL WHERE image_id=?", (cluster_id, image_id))
    conn.commit()


def ensure_cluster(conn: sqlite3.Connection, cluster_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO clusters(cluster_id, created_at, name) VALUES(?, ?, NULL)",
        (cluster_id, utc_now_iso()),
    )
    conn.commit()


def name_cluster(conn: sqlite3.Connection, cluster_id: str, name: str) -> None:
    conn.execute("UPDATE clusters SET name=? WHERE cluster_id=?", (name, cluster_id))
    conn.commit()


def assign_cluster_label(conn: sqlite3.Connection, cluster_id: str, label: str) -> int:
    # Convert all images in cluster to labeled.
    cur = conn.execute("UPDATE images SET label=?, cluster_id=NULL WHERE cluster_id=?", (label, cluster_id))
    conn.commit()
    return int(cur.rowcount or 0)


def list_labels(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT label FROM images WHERE label IS NOT NULL ORDER BY label").fetchall()
    return [str(r[0]) for r in rows if r[0] is not None]


def list_images_by_cluster(conn: sqlite3.Connection, cluster_id: str) -> list[ImageRecord]:
    rows = conn.execute("SELECT * FROM images WHERE cluster_id=? ORDER BY added_at DESC", (cluster_id,)).fetchall()
    return [_row_to_image(r) for r in rows]


def list_unlabeled_clusters(conn: sqlite3.Connection) -> list[ClusterSummary]:
    rows = conn.execute(
        """
        SELECT i.cluster_id AS cluster_id, COUNT(*) AS c, c.name AS name
        FROM images i
        LEFT JOIN clusters c ON c.cluster_id = i.cluster_id
        WHERE i.cluster_id IS NOT NULL
        GROUP BY i.cluster_id
        ORDER BY c DESC
        """
    ).fetchall()
    out: list[ClusterSummary] = []
    for r in rows:
        out.append(ClusterSummary(cluster_id=str(r["cluster_id"]), count=int(r["c"]), name=r["name"]))
    return out


def list_labeled(conn: sqlite3.Connection) -> list[ImageRecord]:
    rows = conn.execute("SELECT * FROM images WHERE label IS NOT NULL").fetchall()
    return [_row_to_image(r) for r in rows]


def get_image(conn: sqlite3.Connection, image_id: int) -> Optional[ImageRecord]:
    row = conn.execute("SELECT * FROM images WHERE image_id=?", (image_id,)).fetchone()
    return _row_to_image(row) if row else None


def _row_to_image(row) -> ImageRecord:
    return ImageRecord(
        image_id=int(row["image_id"]),
        path=Path(str(row["path"])),
        added_at=datetime.fromisoformat(str(row["added_at"])),
        label=row["label"],
        cluster_id=row["cluster_id"],
        embedding_key=str(row["embedding_key"]),
    )
