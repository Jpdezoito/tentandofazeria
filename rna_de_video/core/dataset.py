from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rna_de_video.core.models import ClusterSummary, VideoRecord


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
        CREATE TABLE IF NOT EXISTS videos (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            added_at TEXT NOT NULL,
            label TEXT NULL,
            cluster_id TEXT NULL,
            duration_s REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS video_embeddings (
            video_id INTEGER NOT NULL,
            mode TEXT NOT NULL,
            start_ms INTEGER NOT NULL DEFAULT -1,
            end_ms INTEGER NOT NULL DEFAULT -1,
            created_at TEXT NOT NULL,
            embedding_key TEXT NOT NULL,
            n_frames INTEGER NOT NULL,
            label TEXT NULL,
            cluster_id TEXT NULL,
            PRIMARY KEY(video_id, mode, start_ms, end_ms),
            FOREIGN KEY(video_id) REFERENCES videos(video_id)
        );

        CREATE INDEX IF NOT EXISTS idx_videos_label ON videos(label);
        CREATE INDEX IF NOT EXISTS idx_videos_cluster ON videos(cluster_id);
        CREATE INDEX IF NOT EXISTS idx_video_embeddings_mode ON video_embeddings(mode);
        CREATE INDEX IF NOT EXISTS idx_video_embeddings_mode_seg ON video_embeddings(mode, start_ms, end_ms);
        CREATE INDEX IF NOT EXISTS idx_video_embeddings_label ON video_embeddings(label);
        CREATE INDEX IF NOT EXISTS idx_video_embeddings_cluster ON video_embeddings(cluster_id);

        CREATE TABLE IF NOT EXISTS clusters (
            cluster_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            name TEXT NULL
        );
        """
    )
    conn.commit()

    _migrate_legacy_embeddings(conn)
    _migrate_video_embeddings_segments(conn)
    _migrate_video_embeddings_labels(conn)


def _migrate_video_embeddings_labels(conn: sqlite3.Connection) -> None:
    """Ensure video_embeddings has label/cluster_id and backfill from videos.

    Newer schema stores labels per (video, mode, segment). Older DBs stored labels on videos.
    """

    cols = [r[1] for r in conn.execute("PRAGMA table_info(video_embeddings)").fetchall()]
    changed = False
    if "label" not in cols:
        conn.execute("ALTER TABLE video_embeddings ADD COLUMN label TEXT NULL")
        changed = True
    if "cluster_id" not in cols:
        conn.execute("ALTER TABLE video_embeddings ADD COLUMN cluster_id TEXT NULL")
        changed = True
    if changed:
        conn.commit()

    # Backfill any missing label/cluster_id from legacy videos table.
    conn.execute(
        """
        UPDATE video_embeddings
        SET
            label = COALESCE(label, (SELECT v.label FROM videos v WHERE v.video_id = video_embeddings.video_id)),
            cluster_id = COALESCE(cluster_id, (SELECT v.cluster_id FROM videos v WHERE v.video_id = video_embeddings.video_id))
        WHERE label IS NULL OR cluster_id IS NULL
        """
    )
    conn.commit()


def _migrate_video_embeddings_segments(conn: sqlite3.Connection) -> None:
    """Migrate video_embeddings table to include start_ms/end_ms and new PK.

    Older DBs had PRIMARY KEY(video_id, mode) without segment columns.
    """

    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(video_embeddings)").fetchall()]
    except Exception:
        return

    if "start_ms" in cols and "end_ms" in cols:
        return

    # Rebuild table with new schema
    conn.executescript(
        """
        ALTER TABLE video_embeddings RENAME TO video_embeddings_old;

        CREATE TABLE IF NOT EXISTS video_embeddings (
            video_id INTEGER NOT NULL,
            mode TEXT NOT NULL,
            start_ms INTEGER NOT NULL DEFAULT -1,
            end_ms INTEGER NOT NULL DEFAULT -1,
            created_at TEXT NOT NULL,
            embedding_key TEXT NOT NULL,
            n_frames INTEGER NOT NULL,
            label TEXT NULL,
            cluster_id TEXT NULL,
            PRIMARY KEY(video_id, mode, start_ms, end_ms),
            FOREIGN KEY(video_id) REFERENCES videos(video_id)
        );

         INSERT INTO video_embeddings(video_id, mode, start_ms, end_ms, created_at, embedding_key, n_frames, label, cluster_id)
         SELECT video_id, mode, -1 AS start_ms, -1 AS end_ms, created_at, embedding_key, n_frames,
             (SELECT v.label FROM videos v WHERE v.video_id = video_embeddings_old.video_id) AS label,
             (SELECT v.cluster_id FROM videos v WHERE v.video_id = video_embeddings_old.video_id) AS cluster_id
        FROM video_embeddings_old;

        DROP TABLE video_embeddings_old;

        CREATE INDEX IF NOT EXISTS idx_video_embeddings_mode ON video_embeddings(mode);
        CREATE INDEX IF NOT EXISTS idx_video_embeddings_mode_seg ON video_embeddings(mode, start_ms, end_ms);
        CREATE INDEX IF NOT EXISTS idx_video_embeddings_label ON video_embeddings(label);
        CREATE INDEX IF NOT EXISTS idx_video_embeddings_cluster ON video_embeddings(cluster_id);
        """
    )
    conn.commit()


def _migrate_legacy_embeddings(conn: sqlite3.Connection) -> None:
    """Migrate from old schema where videos had embedding_key/n_frames columns."""

    cols = [r[1] for r in conn.execute("PRAGMA table_info(videos)").fetchall()]
    if "embedding_key" not in cols or "n_frames" not in cols:
        return

    rows = conn.execute(
        "SELECT video_id, embedding_key, n_frames FROM videos WHERE embedding_key IS NOT NULL"
    ).fetchall()
    for r in rows:
        vid = int(r[0])
        key = str(r[1])
        nf = int(r[2])
        conn.execute(
            "INSERT OR IGNORE INTO video_embeddings(video_id, mode, created_at, embedding_key, n_frames) VALUES(?, ?, ?, ?, ?)",
            (vid, "appearance", utc_now_iso(), key, nf),
        )
    conn.commit()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_video(
    conn: sqlite3.Connection,
    *,
    path: Path,
    duration_s: float,
    label: Optional[str] = None,
    cluster_id: Optional[str] = None,
) -> VideoRecord:
    p = str(path.resolve())
    conn.execute(
        "INSERT OR IGNORE INTO videos(path, added_at, label, cluster_id, duration_s) VALUES(?, ?, ?, ?, ?)",
        (p, utc_now_iso(), label, cluster_id, float(duration_s)),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM videos WHERE path=?", (p,)).fetchone()
    if row is None:
        raise RuntimeError("Falha ao inserir vídeo.")
    return _row_to_video(row)


def set_embedding(
    conn: sqlite3.Connection,
    *,
    video_id: int,
    mode: str,
    embedding_key: str,
    n_frames: int,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> None:
    s = int(start_ms) if start_ms is not None else -1
    e = int(end_ms) if end_ms is not None else -1
    conn.execute(
        """
        INSERT INTO video_embeddings(
            video_id, mode, start_ms, end_ms, created_at, embedding_key, n_frames
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id, mode, start_ms, end_ms)
        DO UPDATE SET
            created_at=excluded.created_at,
            embedding_key=excluded.embedding_key,
            n_frames=excluded.n_frames
        """,
        (int(video_id), str(mode), s, e, utc_now_iso(), str(embedding_key), int(n_frames)),
    )
    conn.commit()


def get_embedding_key(
    conn: sqlite3.Connection,
    *,
    video_id: int,
    mode: str,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> Optional[str]:
    s = int(start_ms) if start_ms is not None else -1
    e = int(end_ms) if end_ms is not None else -1
    row = conn.execute(
        "SELECT embedding_key FROM video_embeddings WHERE video_id=? AND mode=? AND start_ms=? AND end_ms=?",
        (int(video_id), str(mode), s, e),
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def list_labeled_embedding_keys(conn: sqlite3.Connection, *, mode: str) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT e.label AS label, e.embedding_key AS embedding_key
        FROM video_embeddings e
        WHERE e.label IS NOT NULL AND e.mode = ?
        """,
        (str(mode),),
    ).fetchall()

    out: list[tuple[str, str]] = []
    for r in rows:
        out.append((str(r["label"]), str(r["embedding_key"])))
    return out


def get_video(conn: sqlite3.Connection, video_id: int) -> Optional[VideoRecord]:
    row = conn.execute("SELECT * FROM videos WHERE video_id=?", (int(video_id),)).fetchone()
    return _row_to_video(row) if row else None


def set_label(conn: sqlite3.Connection, video_id: int, label: Optional[str]) -> None:
    # Legacy behavior: applies to all segments/modes of this video.
    conn.execute(
        "UPDATE video_embeddings SET label=?, cluster_id=NULL WHERE video_id=?",
        (label, int(video_id)),
    )
    conn.commit()


def set_label_for_segment(
    conn: sqlite3.Connection,
    *,
    video_id: int,
    mode: str,
    start_ms: int | None,
    end_ms: int | None,
    label: Optional[str],
) -> None:
    s = int(start_ms) if start_ms is not None else -1
    e = int(end_ms) if end_ms is not None else -1
    conn.execute(
        """
        UPDATE video_embeddings
        SET label=?, cluster_id=NULL
        WHERE video_id=? AND mode=? AND start_ms=? AND end_ms=?
        """,
        (label, int(video_id), str(mode), s, e),
    )
    conn.commit()


def set_cluster(conn: sqlite3.Connection, video_id: int, cluster_id: Optional[str]) -> None:
    # Legacy behavior: applies to all segments/modes of this video.
    conn.execute(
        "UPDATE video_embeddings SET cluster_id=?, label=NULL WHERE video_id=?",
        (cluster_id, int(video_id)),
    )
    conn.commit()


def set_cluster_for_segment(
    conn: sqlite3.Connection,
    *,
    video_id: int,
    mode: str,
    start_ms: int | None,
    end_ms: int | None,
    cluster_id: Optional[str],
) -> None:
    s = int(start_ms) if start_ms is not None else -1
    e = int(end_ms) if end_ms is not None else -1
    conn.execute(
        """
        UPDATE video_embeddings
        SET cluster_id=?, label=NULL
        WHERE video_id=? AND mode=? AND start_ms=? AND end_ms=?
        """,
        (cluster_id, int(video_id), str(mode), s, e),
    )
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
    cur = conn.execute(
        "UPDATE video_embeddings SET label=?, cluster_id=NULL WHERE cluster_id=?",
        (label, cluster_id),
    )
    conn.commit()
    return int(cur.rowcount or 0)


def list_labels(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT label FROM video_embeddings WHERE label IS NOT NULL ORDER BY label").fetchall()
    return [str(r[0]) for r in rows if r[0] is not None]


def list_labeled(conn: sqlite3.Connection) -> list[VideoRecord]:
    rows = conn.execute("SELECT * FROM videos WHERE label IS NOT NULL").fetchall()
    return [_row_to_video(r) for r in rows]


def list_unlabeled_clusters(conn: sqlite3.Connection) -> list[ClusterSummary]:
    rows = conn.execute(
        """
        SELECT e.cluster_id AS cluster_id, COUNT(*) AS c, c.name AS name
        FROM video_embeddings e
        LEFT JOIN clusters c ON c.cluster_id = e.cluster_id
        WHERE e.cluster_id IS NOT NULL AND e.label IS NULL
        GROUP BY e.cluster_id
        ORDER BY c DESC
        """
    ).fetchall()

    out: list[ClusterSummary] = []
    for r in rows:
        out.append(ClusterSummary(cluster_id=str(r["cluster_id"]), count=int(r["c"]), name=r["name"]))
    return out


def list_videos_by_cluster(conn: sqlite3.Connection, cluster_id: str) -> list[tuple[Path, str, int, int]]:
    rows = conn.execute(
        """
        SELECT v.path AS path, e.mode AS mode, e.start_ms AS start_ms, e.end_ms AS end_ms
        FROM video_embeddings e
        JOIN videos v ON v.video_id = e.video_id
        WHERE e.cluster_id=? AND e.label IS NULL
        ORDER BY e.created_at DESC
        """,
        (cluster_id,),
    ).fetchall()

    out: list[tuple[Path, str, int, int]] = []
    for r in rows:
        out.append((Path(str(r["path"])), str(r["mode"]), int(r["start_ms"]), int(r["end_ms"])))
    return out


def _row_to_video(row) -> VideoRecord:
    # Back-compat: old DB had embedding_key/n_frames columns.
    embedding_key = ""
    n_frames = 0
    try:
        embedding_key = str(row["embedding_key"]) if "embedding_key" in row.keys() else ""
        n_frames = int(row["n_frames"]) if "n_frames" in row.keys() else 0
    except Exception:
        embedding_key = ""
        n_frames = 0

    return VideoRecord(
        video_id=int(row["video_id"]),
        path=Path(str(row["path"])),
        added_at=datetime.fromisoformat(str(row["added_at"])),
        label=row["label"],
        embedding_key=embedding_key,
        n_frames=n_frames,
        duration_s=float(row["duration_s"]),
    )
