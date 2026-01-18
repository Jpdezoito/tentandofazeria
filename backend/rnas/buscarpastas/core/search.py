from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from core.config import AppConfig
from core.index_db import query_candidates
from core.models import ItemKind, SearchResult
from core.normalize import normalize_name_for_index, normalize_text
from core.storage import PreferenceStore


def _try_rapidfuzz_ratio(a: str, b: str) -> Optional[float]:
    try:
        from rapidfuzz.fuzz import ratio  # type: ignore

        return float(ratio(a, b))
    except Exception:
        return None


def _difflib_ratio(a: str, b: str) -> float:
    import difflib

    return 100.0 * difflib.SequenceMatcher(None, a, b).ratio()


def fuzzy_ratio(a: str, b: str) -> float:
    rf = _try_rapidfuzz_ratio(a, b)
    if rf is not None:
        return rf
    return _difflib_ratio(a, b)


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _source_weight(source: str) -> float:
    if source in {"desktop", "public_desktop"}:
        return 18.0
    if source.startswith("startmenu"):
        return 14.0
    if source in {"documents", "downloads", "pictures", "videos"}:
        return 9.0
    if source.startswith("programfiles"):
        return 6.0
    if source.startswith("appdata"):
        return 1.0
    if source.startswith("drive_"):
        return -2.0
    return 0.0


def _usage_boost(count: int, last_opened_iso: Optional[str]) -> float:
    boost = 0.0
    if count > 0:
        boost += 6.0 * math.log1p(count)

    dt = _parse_iso(last_opened_iso)
    if dt:
        age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
        # Recent opens get more boost; decays with time.
        boost += 18.0 * math.exp(-age_days / 7.0)

    return boost


@dataclass(frozen=True)
class SearchParams:
    query_text: str
    query_norm: str
    action: str  # open/execute (used only for minor heuristics)


def search(
    conn,
    store: PreferenceStore,
    config: AppConfig,
    params: SearchParams,
    cancel_event,
    log: Callable[[str], None] | None = None,
) -> list[SearchResult]:
    """Search indexed items + aliases and return ranked suggestions."""

    query_norm = params.query_norm.strip() or normalize_text(params.query_text)
    if not query_norm:
        return []

    # 1) Preference for this exact command (learned)
    preferred_path = store.get_preference_for_query(query_norm)

    # 2) Manual aliases (normalized)
    aliases = store.load_aliases()
    aliases_norm = {normalize_text(k): v for k, v in aliases.items()}

    results: list[SearchResult] = []

    def add_path_as_result(path_str: str, reason: str, score: float) -> None:
        p = Path(path_str)
        if not p.exists():
            return
        kind = ItemKind.FOLDER if p.is_dir() else ItemKind.FILE
        ext = p.suffix.lower()
        if ext in config.shortcut_exts:
            kind = ItemKind.SHORTCUT
        elif ext in config.executable_exts:
            kind = ItemKind.EXECUTABLE
        results.append(
            SearchResult(
                path=p,
                display_name=p.name,
                kind=kind,
                source="alias",
                score=score,
                reason=reason,
            )
        )

    if preferred_path:
        add_path_as_result(preferred_path, reason="preferência salva", score=1000.0)

    if query_norm in aliases_norm:
        add_path_as_result(aliases_norm[query_norm], reason="alias exato", score=900.0)

    # If user typed something like "planilha.xlsx", try to filter by ext.
    ext_filter: Optional[str] = None
    if "." in params.query_text:
        ext = Path(params.query_text.strip()).suffix.lower()
        if ext:
            ext_filter = ext

    token = query_norm.split()[0]
    if log:
        log(f"Buscando candidatos por token: '{token}'")

    # Pull a broad candidate set and score in Python.
    candidate_rows = query_candidates(conn, token=token, limit=800, ext_filter=ext_filter)

    for row in candidate_rows:
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Busca cancelada.")
            return []

        p = Path(row["path"])
        display_name = str(row["display_name"])
        name_norm = str(row["name_norm"]) or normalize_name_for_index(display_name)
        kind_str = str(row["kind"])
        source = str(row["source"])

        kind = {
            "file": ItemKind.FILE,
            "folder": ItemKind.FOLDER,
            "executable": ItemKind.EXECUTABLE,
            "shortcut": ItemKind.SHORTCUT,
        }.get(kind_str, ItemKind.FILE)

        base = fuzzy_ratio(query_norm, name_norm)
        if base < config.min_fuzzy_score:
            continue

        count, last_opened = store.get_usage(str(p))
        score = base
        score += _source_weight(source)
        score += _usage_boost(count, last_opened)

        # Extra: exact filename match gets a bump
        if params.query_text.strip().lower() == display_name.lower():
            score += 25.0

        results.append(
            SearchResult(
                path=p,
                display_name=display_name,
                kind=kind,
                source=source,
                score=score,
                reason=f"fuzzy={base:.1f} src={source}",
            )
        )

    # De-dup by path keeping best score.
    best: dict[str, SearchResult] = {}
    for r in results:
        k = str(r.path)
        if k not in best or r.score > best[k].score:
            best[k] = r

    ranked = sorted(best.values(), key=lambda r: r.score, reverse=True)
    ranked = ranked[: config.max_results]

    if log:
        log(f"Resultados: {len(ranked)}")

    return ranked
