from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def _env_flag(name: str) -> bool:
    import os

    v = str(os.environ.get(name, "")).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class AppConfig:
    """Configuration for indexing/search behavior."""

    app_name: str = "RNA"

    # Folder policy
    # The assistant tries to locate a folder named like this next to main.py.
    # If it does not exist, it will be created under the project root.
    project_folder_name: str = "treino_rna_buscarpastas"
    treinos_dir_name: str = "treinos"

    # Data locations (relative to treinos dir)
    index_db_name: str = "index.db"
    aliases_json_name: str = "aliases.json"
    stats_json_name: str = "stats.json"

    cache_dir_name: str = "cache"
    logs_dir_name: str = "logs"

    # Indexing limits
    max_files_per_root: int = 250_000
    max_drive_files_total: int = 250_000
    max_drive_scan_seconds: float = 45.0

    # Search
    max_results: int = 25
    min_fuzzy_score: int = 55

    # Layer 2 (limited on-demand search)
    limited_max_depth: int = 3
    limited_max_entries: int = 80_000
    limited_timeout_seconds: float = 8.0

    # Local drives (C:, D:...) scanning
    enable_drive_scan: bool = True

    # File types considered executable (safe-ish to launch)
    executable_exts: tuple[str, ...] = (".exe", ".bat", ".cmd", ".com", ".ps1")
    shortcut_exts: tuple[str, ...] = (".lnk",)


def config_from_env() -> AppConfig:
    """Build config with safe defaults when debugging.

    Set IANOVA_SAFE_DEBUG=1 to reduce CPU/disk-heavy operations.
    """

    if not _env_flag("IANOVA_SAFE_DEBUG"):
        return AppConfig()

    return AppConfig(
        enable_drive_scan=False,
        max_files_per_root=35_000,
        max_drive_files_total=25_000,
        max_drive_scan_seconds=6.0,
        limited_max_depth=2,
        limited_max_entries=15_000,
        limited_timeout_seconds=2.0,
        max_results=15,
    )


def project_root() -> Path:
    """Return the assumed project root (directory containing main.py).

    Works when running from the repo root.
    """

    return Path(__file__).resolve().parents[1]


def assistant_base_dir(config: AppConfig) -> Path:
    """Return the base folder that contains the project.

    Rules:
    - If a folder named config.project_folder_name exists *alongside* main.py, use it.
    - Else, if the current project root already is that folder, use it.
    - Else, create it under the project root.
    """

    root = project_root()

    if root.name.lower() == config.project_folder_name.lower():
        return root

    candidate = root / config.project_folder_name
    if candidate.exists() and candidate.is_dir():
        return candidate

    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def treinos_dir(config: AppConfig) -> Path:
    d = assistant_base_dir(config) / config.treinos_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def modelo_treino_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / "modelo_treino"
    d.mkdir(parents=True, exist_ok=True)
    return d


def modelos_pre_treinados_dir(config: AppConfig) -> Path:
    d = modelo_treino_dir(config) / "modelos_pre_treinados"
    d.mkdir(parents=True, exist_ok=True)
    return d


def active_pretrained_root(config: AppConfig) -> Path | None:
    """Return the active pretrained bundle folder if configured.

    Rules (first match wins):
    - treinos/modelo_treino/modelos_pre_treinados/ATIVO.txt containing a relative folder name
    - treinos/modelo_treino/modelos_pre_treinados/ativo (directory)

    The active folder can contain index.db, aliases.json, stats.json, etc.
    """

    base = modelos_pre_treinados_dir(config)
    marker = base / "ATIVO.txt"
    if marker.exists():
        rel = marker.read_text(encoding="utf-8", errors="replace").strip()
        if rel:
            candidate = (base / rel).resolve()
            if candidate.exists() and candidate.is_dir():
                return candidate

    candidate = base / "ativo"
    if candidate.exists() and candidate.is_dir():
        return candidate

    return None


def _prefer_pretrained_file(config: AppConfig, filename: str) -> Path | None:
    active = active_pretrained_root(config)
    if not active:
        return None
    p = active / filename
    return p if p.exists() and p.is_file() else None


def index_db_path(config: AppConfig) -> Path:
    return _prefer_pretrained_file(config, config.index_db_name) or (treinos_dir(config) / config.index_db_name)


def aliases_path(config: AppConfig) -> Path:
    return _prefer_pretrained_file(config, config.aliases_json_name) or (treinos_dir(config) / config.aliases_json_name)


def stats_path(config: AppConfig) -> Path:
    return _prefer_pretrained_file(config, config.stats_json_name) or (treinos_dir(config) / config.stats_json_name)


def cache_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.cache_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.logs_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d
