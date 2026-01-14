from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Configuration for the open-world image learner."""

    app_name: str = "RNA_Qualquer_Imagem"

    # Folder policy (everything must stay under treinos/)
    project_folder_name: str = "treino_rna_qualquer_imagem"
    treinos_dir_name: str = "treinos"

    dataset_db_name: str = "dataset.db"
    thresholds_json_name: str = "thresholds.json"
    stats_json_name: str = "stats.json"

    embeddings_cache_dir_name: str = "embeddings_cache"
    model_dir_name: str = "model"
    logs_dir_name: str = "logs"

    # Embeddings
    backbone: str = "resnet50"  # "resnet50" | "efficientnetb0"
    embedding_dim_hint: int = 2048
    image_size: int = 224

    # Novelty detection
    min_top1_confidence: float = 0.55
    min_top1_similarity: float = 0.35

    # Replay buffer
    replay_per_class: int = 50

    # Clustering (unknowns)
    unknown_cluster_similarity: float = 0.55


def project_root() -> Path:
    # Directory containing main.py
    return Path(__file__).resolve().parents[1]


def assistant_base_dir(config: AppConfig) -> Path:
    """Return base folder.

    If a folder named config.project_folder_name exists next to main.py, use it.
    Otherwise, create it under the project root.
    """

    root = project_root()
    if root.name.lower() == config.project_folder_name.lower():
        return root

    candidate = root / config.project_folder_name
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

    The active folder can contain files/dirs like:
    - model/ (saved model)
    - embeddings_cache/
    - thresholds.json, stats.json, dataset.db
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


def _prefer_pretrained_dir(config: AppConfig, dirname: str) -> Path | None:
    active = active_pretrained_root(config)
    if not active:
        return None
    p = active / dirname
    return p if p.exists() and p.is_dir() else None


def dataset_db_path(config: AppConfig) -> Path:
    return _prefer_pretrained_file(config, config.dataset_db_name) or (treinos_dir(config) / config.dataset_db_name)


def thresholds_path(config: AppConfig) -> Path:
    return _prefer_pretrained_file(config, config.thresholds_json_name) or (treinos_dir(config) / config.thresholds_json_name)


def stats_path(config: AppConfig) -> Path:
    return _prefer_pretrained_file(config, config.stats_json_name) or (treinos_dir(config) / config.stats_json_name)


def embeddings_cache_dir(config: AppConfig) -> Path:
    pretrained = _prefer_pretrained_dir(config, config.embeddings_cache_dir_name)
    if pretrained:
        return pretrained

    d = treinos_dir(config) / config.embeddings_cache_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def model_dir(config: AppConfig) -> Path:
    pretrained = _prefer_pretrained_dir(config, config.model_dir_name)
    if pretrained:
        return pretrained

    d = treinos_dir(config) / config.model_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.logs_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d
