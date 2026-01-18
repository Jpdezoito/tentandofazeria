from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from core.config import AppConfig
from core.models import ItemKind, SearchResult
from core.normalize import normalize_name_for_index, normalize_text
from core.search import fuzzy_ratio
from core.storage import PreferenceStore
from core.windows_paths import get_standard_roots

LogFn = Callable[[str], None]


@dataclass(frozen=True)
class QuickSearchParams:
    query_text: str
    query_norm: str
    action: str  # open/execute


def _classify_path(p: Path, config: AppConfig) -> ItemKind:
    if p.is_dir():
        return ItemKind.FOLDER
    ext = p.suffix.lower()
    if ext in config.shortcut_exts:
        return ItemKind.SHORTCUT
    if ext in config.executable_exts:
        return ItemKind.EXECUTABLE
    return ItemKind.FILE


def _add_if_match(
    results: list[SearchResult],
    p: Path,
    query_norm: str,
    source: str,
    config: AppConfig,
    min_score: float,
) -> None:
    name_norm = normalize_name_for_index(p.name)
    score = fuzzy_ratio(query_norm, name_norm)
    if score < min_score:
        return
    results.append(
        SearchResult(
            path=p,
            display_name=p.name,
            kind=_classify_path(p, config),
            source=source,
            score=score,
            reason=f"camada1 fuzzy={score:.1f}",
        )
    )


def _iter_shallow(root: Path, max_items: int = 350) -> Iterable[Path]:
    """Shallow listing of a directory (non-recursive) with a limit."""

    count = 0
    try:
        with os.scandir(root) as it:
            for entry in it:
                if count >= max_items:
                    return
                count += 1
                yield Path(entry.path)
    except (FileNotFoundError, PermissionError, OSError):
        return


def _iter_startmenu_links(root: Path, max_items: int = 5_000) -> Iterable[Path]:
    """Recursive but bounded walk of Start Menu Programs (mainly .lnk)."""

    stack: list[Path] = [root]
    seen = 0
    while stack and seen < max_items:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if seen >= max_items:
                        return
                    seen += 1
                    p = Path(entry.path)
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(p)
                        else:
                            if p.suffix.lower() in {".lnk", ".exe"}:
                                yield p
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
        except (PermissionError, FileNotFoundError, OSError):
            continue


def _common_executable_candidates(query_norm: str) -> list[Path]:
    """Small curated set of common executable paths (no full scan)."""

    # Map normalized tokens to executable names.
    token = query_norm.split()[0] if query_norm.split() else query_norm
    token = token.replace(".exe", "")

    candidates: list[Path] = []

    # Common patterns
    pf = os.environ.get("ProgramFiles")
    pf86 = os.environ.get("ProgramFiles(x86)")

    def add(*parts: str) -> None:
        p = Path(*parts)
        candidates.append(p)

    if token in {"chrome", "google chrome"}:
        if pf:
            add(pf, "Google", "Chrome", "Application", "chrome.exe")
        if pf86:
            add(pf86, "Google", "Chrome", "Application", "chrome.exe")
    if token in {"discord"}:
        # Discord often lives under AppData, but we won't scan it; use known path.
        up = os.environ.get("USERPROFILE")
        if up:
            candidates.append(Path(up) / "AppData" / "Local" / "Discord" / "Update.exe")
    if token in {"word", "winword"}:
        if pf:
            candidates.append(Path(pf) / "Microsoft Office" / "root" / "Office16" / "WINWORD.EXE")
    if token in {"excel"}:
        if pf:
            candidates.append(Path(pf) / "Microsoft Office" / "root" / "Office16" / "EXCEL.EXE")

    # Generic: if user typed an exe name, try in a couple common roots.
    if token and token.isascii() and " " not in token:
        exe_name = token if token.endswith(".exe") else f"{token}.exe"
        if pf:
            candidates.append(Path(pf) / exe_name)
        if pf86:
            candidates.append(Path(pf86) / exe_name)

    # Deduplicate
    out: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        k = str(p).lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def quick_search(
    store: PreferenceStore,
    config: AppConfig,
    params: QuickSearchParams,
    log: Optional[LogFn] = None,
) -> list[SearchResult]:
    """Layer 1: instant/cheap search.

    Order:
    - learned preference (exact query_norm)
    - manual aliases
    - shallow scan: Desktop + standard folders
    - Start Menu shortcuts (.lnk)
    - short curated candidate executable paths
    """

    t0 = time.perf_counter()
    query_norm = params.query_norm.strip() or normalize_text(params.query_text)
    if not query_norm:
        return []

    results: list[SearchResult] = []

    if log:
        log("Camada 1: preferência/aliases...")

    pref = store.get_preference_for_query(query_norm)
    if pref:
        p = Path(pref)
        if p.exists():
            results.append(
                SearchResult(
                    path=p,
                    display_name=p.name,
                    kind=_classify_path(p, config),
                    source="preferencia",
                    score=1000.0,
                    reason="preferência salva",
                )
            )
            return results

    aliases = store.load_aliases()
    aliases_norm = {normalize_text(k): v for k, v in aliases.items()}
    alias_path = aliases_norm.get(query_norm)
    if alias_path:
        p = Path(alias_path)
        if p.exists():
            results.append(
                SearchResult(
                    path=p,
                    display_name=p.name,
                    kind=_classify_path(p, config),
                    source="alias",
                    score=900.0,
                    reason="alias exato",
                )
            )
            return results

    # Shallow scans in standard roots
    roots = get_standard_roots()

    if log:
        log("Camada 1: buscando em Desktop e pastas padrão (varredura rasa)...")

    for r in roots:
        # Skip heavy roots here; keep it instant.
        if r.name.startswith("programfiles") or r.name.startswith("appdata") or r.name.startswith("drive_"):
            continue
        if r.name.startswith("startmenu"):
            continue

        for p in _iter_shallow(r.path, max_items=600):
            _add_if_match(results, p, query_norm=query_norm, source=r.name, config=config, min_score=78.0)

    # Start Menu shortcuts (still bounded)
    if log:
        log("Camada 1: buscando em Start Menu (.lnk)...")

    for r in roots:
        if not r.name.startswith("startmenu"):
            continue
        for p in _iter_startmenu_links(r.path, max_items=6_000):
            _add_if_match(results, p, query_norm=query_norm, source=r.name, config=config, min_score=76.0)

    # Common short paths for known executables
    if log:
        log("Camada 1: buscando em caminhos curtos comuns (sem varrer tudo)...")

    for candidate in _common_executable_candidates(query_norm):
        if candidate.exists():
            results.append(
                SearchResult(
                    path=candidate,
                    display_name=candidate.name,
                    kind=_classify_path(candidate, config),
                    source="candidato_curto",
                    score=820.0,
                    reason="caminho candidato",
                )
            )

    # Rank layer 1 results by score then by source preference
    ranked = sorted(results, key=lambda r: r.score, reverse=True)
    ranked = ranked[: config.max_results]

    if log:
        log(f"Camada 1: {len(ranked)} resultado(s) em {(time.perf_counter() - t0) * 1000:.0f}ms")

    return ranked
