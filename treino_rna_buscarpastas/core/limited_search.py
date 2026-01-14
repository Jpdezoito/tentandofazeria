from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import threading

from core.config import AppConfig
from core.models import ItemKind, SearchResult
from core.normalize import normalize_name_for_index, normalize_text
from core.search import fuzzy_ratio
from core.windows_paths import get_standard_roots

LogFn = Callable[[str], None]


@dataclass(frozen=True)
class LimitedSearchConfig:
    max_depth: int = 3
    max_entries: int = 80_000
    timeout_seconds: float = 8.0


_FORBIDDEN_DIR_SUBSTRINGS = [
    "\\windows\\",
    "\\$recycle.bin\\",
    "\\system volume information\\",
    "\\programdata\\package cache\\",
    "\\appdata\\local\\temp\\",
    "\\temp\\",
    "\\microsoft\\edgewebview\\",
]


def _is_forbidden_dir(path: Path) -> bool:
    p = str(path).lower().replace("/", "\\")
    return any(s in p for s in _FORBIDDEN_DIR_SUBSTRINGS)


def _classify_path(p: Path, config: AppConfig) -> ItemKind:
    if p.is_dir():
        return ItemKind.FOLDER
    ext = p.suffix.lower()
    if ext in config.shortcut_exts:
        return ItemKind.SHORTCUT
    if ext in config.executable_exts:
        return ItemKind.EXECUTABLE
    return ItemKind.FILE


def limited_search(
    config: AppConfig,
    query_text: str,
    query_norm: str,
    cancel_event: Optional[threading.Event],
    log: Optional[LogFn] = None,
    limits: LimitedSearchConfig = LimitedSearchConfig(),
) -> list[SearchResult]:
    """Layer 2: bounded search with max depth + time/entry limits.

    This does NOT use the full index; it walks selected roots in a controlled way.
    """

    t0 = time.perf_counter()
    qn = query_norm.strip() or normalize_text(query_text)
    if not qn:
        return []

    token = qn.split()[0] if qn.split() else qn
    want_exts: set[str] = set()

    # Heuristic: if user seems to be asking for an app, prefer exe/lnk.
    if "." in query_text:
        ext = Path(query_text.strip()).suffix.lower()
        if ext:
            want_exts.add(ext)
    else:
        # Common: open/execute app name
        want_exts.update({".lnk", ".exe"})

    if log:
        log(
            f"Camada 2: busca limitada (prof={limits.max_depth}, max={limits.max_entries}, timeout={limits.timeout_seconds:.1f}s)..."
        )

    roots = get_standard_roots()

    # In camada 2 we allow Program Files but still bounded and with forbidden directories.
    allowed_roots = [
        r
        for r in roots
        if (
            r.name
            in {
                "desktop",
                "public_desktop",
                "documents",
                "downloads",
                "pictures",
                "videos",
                "startmenu_user",
                "startmenu_programdata",
                "programfiles",
                "programfiles_x86",
            }
        )
    ]

    deadline = time.perf_counter() + limits.timeout_seconds
    results: list[SearchResult] = []

    scanned = 0

    for root in allowed_roots:
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Camada 2: cancelado.")
            return []

        if log:
            log(f"Camada 2: raiz {root.name} -> {root.path}")

        # BFS with depth
        queue: list[tuple[Path, int]] = [(root.path, 0)]

        while queue:
            if time.perf_counter() > deadline:
                if log:
                    log("Camada 2: timeout atingido.")
                return _rank(results, config)

            if cancel_event is not None and cancel_event.is_set():
                if log:
                    log("Camada 2: cancelado.")
                return []

            current, depth = queue.pop(0)
            if depth > limits.max_depth:
                continue
            if _is_forbidden_dir(current):
                continue

            try:
                with os.scandir(current) as it:
                    for entry in it:
                        scanned += 1
                        if scanned >= limits.max_entries:
                            if log:
                                log("Camada 2: limite de entradas atingido.")
                            return _rank(results, config)

                        if time.perf_counter() > deadline:
                            if log:
                                log("Camada 2: timeout atingido.")
                            return _rank(results, config)

                        if cancel_event is not None and cancel_event.is_set():
                            if log:
                                log("Camada 2: cancelado.")
                            return []

                        p = Path(entry.path)
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if not _is_forbidden_dir(p):
                                    queue.append((p, depth + 1))
                                # Directories are also valid results (pasta projetos, etc.)
                                score = fuzzy_ratio(qn, normalize_name_for_index(p.name))
                                if score >= 86.0:
                                    results.append(
                                        SearchResult(
                                            path=p,
                                            display_name=p.name,
                                            kind=ItemKind.FOLDER,
                                            source=root.name,
                                            score=score,
                                            reason="camada2 dir",
                                        )
                                    )
                            else:
                                ext = p.suffix.lower()
                                # If we're hunting apps, filter.
                                if want_exts and ext and ext not in want_exts:
                                    continue

                                name_norm = normalize_name_for_index(p.name)
                                score = fuzzy_ratio(qn, name_norm)
                                # Use a stricter threshold to keep results sane.
                                if score < 72.0:
                                    continue

                                # Quick token check to reduce noise.
                                if token and token not in name_norm:
                                    # still allow very high fuzzy
                                    if score < 90.0:
                                        continue

                                results.append(
                                    SearchResult(
                                        path=p,
                                        display_name=p.name,
                                        kind=_classify_path(p, config),
                                        source=root.name,
                                        score=score,
                                        reason="camada2 file",
                                    )
                                )
                        except (PermissionError, FileNotFoundError, OSError):
                            continue

            except (PermissionError, FileNotFoundError, OSError):
                continue

    if log:
        log(f"Camada 2: {len(results)} match(es) em {(time.perf_counter() - t0):.1f}s")

    return _rank(results, config)


def _rank(results: list[SearchResult], config: AppConfig) -> list[SearchResult]:
    # De-dupe by path keeping max score.
    best: dict[str, SearchResult] = {}
    for r in results:
        k = str(r.path).lower()
        if k not in best or r.score > best[k].score:
            best[k] = r

    ranked = sorted(best.values(), key=lambda r: r.score, reverse=True)
    return ranked[: config.max_results]
