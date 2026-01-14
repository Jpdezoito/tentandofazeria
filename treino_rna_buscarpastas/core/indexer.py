from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Iterator

import threading

from core.config import AppConfig
from core.index_db import (
    DbItemRow,
    begin_scan,
    finalize_scan,
    get_existing_mtime_size,
    init_db,
    touch_scan_ids,
    upsert_items,
)
from core.normalize import normalize_name_for_index
from core.windows_paths import SearchRoot, get_standard_roots, iter_local_drives

LogFn = Callable[[str], None]

_SKIP_DIR_NAMES = {
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "temp",
    "inetcache",
    "crashdumps",
}


def _is_probably_hidden(path: Path) -> bool:
    name = path.name
    return name.startswith(".") or name in {"$Recycle.Bin", "System Volume Information"}


def _should_skip_dir(path: Path) -> bool:
    name = path.name.strip().lower()
    return name in _SKIP_DIR_NAMES


def _classify(path: Path, config: AppConfig) -> tuple[str, str]:
    """Return (kind, ext) for DB."""

    if path.is_dir():
        return "folder", ""
    ext = path.suffix.lower()
    if ext in config.shortcut_exts:
        return "shortcut", ext
    if ext in config.executable_exts:
        return "executable", ext
    return "file", ext


def _iter_paths(root: Path, cancel: threading.Event | None, log: LogFn | None) -> Iterator[Path]:
    """Iterate through files and directories under root using a scandir stack."""

    stack: list[Path] = [root]
    while stack:
        if cancel is not None and cancel.is_set():
            return

        current = stack.pop()
        try:
            if log:
                log(f"DIR  {current}")
            with os.scandir(current) as it:
                for entry in it:
                    if cancel is not None and cancel.is_set():
                        return
                    try:
                        p = Path(entry.path)
                        if _is_probably_hidden(p):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if _should_skip_dir(p):
                                continue
                            # Index folders too (helps "abrir pasta X")
                            yield p
                            stack.append(p)
                        else:
                            yield p
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
        except (PermissionError, FileNotFoundError, OSError):
            continue


def build_roots(config: AppConfig) -> list[SearchRoot]:
    roots = get_standard_roots()

    if config.enable_drive_scan:
        for drive in iter_local_drives():
            # Drive scan is expensive; treat each drive as a root.
            roots.append(SearchRoot(f"drive_{drive[0].lower()}", Path(drive)))

    return roots


def index_all(
    conn,
    config: AppConfig,
    cancel_event,
    log: LogFn | None = None,
) -> None:
    """(Re)index all sources.

    This runs in the calling thread; GUI should run this in a worker thread.
    """

    init_db(conn)
    roots = build_roots(config)

    for root in roots:
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Indexação cancelada.")
            return
        index_root(conn, config, root, cancel_event, log)


def index_root(
    conn,
    config: AppConfig,
    root: SearchRoot,
    cancel_event,
    log: LogFn | None = None,
) -> None:
    started = time.perf_counter()
    t0 = time.time()

    scan_id = begin_scan(conn, root.name, started_at=t0)
    if log:
        log(f"== Indexando: {root.name} ==")
        log(str(root.path))

    batch: list[DbItemRow] = []
    touch_paths: list[str] = []
    batch_size = 800
    seen = 0

    drive_mode = root.name.startswith("drive_")
    drive_deadline = time.perf_counter() + float(config.max_drive_scan_seconds)

    pending_stats: list[tuple[Path, os.stat_result]] = []

    def flush_pending() -> None:
        nonlocal batch, touch_paths, pending_stats
        if not pending_stats:
            return
        existing = get_existing_mtime_size(conn, [str(p) for p, _ in pending_stats])

        for p, st in pending_stats:
            kind, ext = _classify(p, config)
            display_name = p.name
            key = str(p)
            prev = existing.get(key)
            mtime = float(st.st_mtime)
            size = int(getattr(st, "st_size", 0) or 0)
            if prev is not None and abs(prev[0] - mtime) < 1e-6 and int(prev[1]) == size:
                touch_paths.append(key)
            else:
                batch.append(
                    DbItemRow(
                        path=key,
                        display_name=display_name,
                        name_norm=normalize_name_for_index(display_name),
                        kind=kind,
                        source=root.name,
                        mtime=mtime,
                        size=size,
                        ext=ext,
                    )
                )

        pending_stats = []

    for p in _iter_paths(root.path, cancel_event, log):
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Indexação cancelada.")
            return

        if drive_mode:
            if time.perf_counter() > drive_deadline:
                if log:
                    log("Limite de tempo atingido para drive; parando scan.")
                break
            if seen >= config.max_drive_files_total:
                if log:
                    log("Limite de arquivos do drive atingido; parando scan.")
                break
        else:
            if seen >= config.max_files_per_root:
                if log:
                    log("Limite de arquivos por raiz atingido; parando scan.")
                break

        try:
            st = p.stat()
            pending_stats.append((p, st))
            seen += 1

            if len(pending_stats) >= batch_size:
                flush_pending()
                if batch:
                    upsert_items(conn, batch, scan_id=scan_id)
                    batch.clear()
                if touch_paths:
                    touch_scan_ids(conn, touch_paths, scan_id=scan_id)
                    touch_paths.clear()
                conn.commit()

        except (PermissionError, FileNotFoundError, OSError):
            continue

    flush_pending()

    if batch:
        upsert_items(conn, batch, scan_id=scan_id)
        batch.clear()
    if touch_paths:
        touch_scan_ids(conn, touch_paths, scan_id=scan_id)
        touch_paths.clear()
    conn.commit()

    finalize_scan(conn, root.name, scan_id)

    elapsed = time.perf_counter() - started
    if log:
        log(f"OK: {root.name} | itens: {seen} | {elapsed:.2f}s")
