from __future__ import annotations

from pathlib import Path

import numpy as np

from core.config import AppConfig, embeddings_cache_dir
from core.utils import embedding_key_for_file


def cache_path_for_key(config: AppConfig, key: str) -> Path:
    return embeddings_cache_dir(config) / f"{key}.npy"


def load_embedding(config: AppConfig, key: str) -> np.ndarray | None:
    p = cache_path_for_key(config, key)
    if not p.exists():
        return None
    try:
        return np.load(p).astype(np.float32)
    except Exception:
        return None


def save_embedding(config: AppConfig, key: str, emb: np.ndarray) -> None:
    p = cache_path_for_key(config, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, emb.astype(np.float32))


def get_or_compute_embedding(config: AppConfig, extractor, image_path: Path) -> tuple[str, np.ndarray]:
    key = embedding_key_for_file(image_path)
    cached = load_embedding(config, key)
    if cached is not None:
        return key, cached

    emb = extractor.extract(image_path)
    save_embedding(config, key, emb)
    return key, emb
