from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "RNA_Video"

    # Folder policy (everything must stay under treinos/)
    project_folder_name: str = "rna_de_video"
    treinos_dir_name: str = "treinos"

    dataset_db_name: str = "dataset.db"
    thresholds_json_name: str = "thresholds.json"

    embeddings_cache_dir_name: str = "embeddings_cache"
    model_dir_name: str = "model"
    logs_dir_name: str = "logs"

    imported_videos_dir_name: str = "imported_videos"

    # URL import
    video_url_timeout_s: float = 30.0
    video_url_max_bytes: int = 250 * 1024 * 1024  # 250MB

    # Video
    max_frames_per_video: int = 16
    min_frame_step_s: float = 0.75
    frame_resize: int = 224

    # Embeddings
    backbone: str = "resnet50"  # resnet50 | fallback_hist

    # Novelty detection
    min_top1_confidence: float = 0.55
    min_top1_similarity: float = 0.33

    # Replay buffer
    replay_per_class: int = 30


def project_root() -> Path:
    # Directory containing main.py
    return Path(__file__).resolve().parents[1]


def assistant_base_dir(config: AppConfig) -> Path:
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


def dataset_db_path(config: AppConfig) -> Path:
    return treinos_dir(config) / config.dataset_db_name


def thresholds_path(config: AppConfig) -> Path:
    return treinos_dir(config) / config.thresholds_json_name


def embeddings_cache_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.embeddings_cache_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def model_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.model_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.logs_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def imported_videos_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.imported_videos_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d
