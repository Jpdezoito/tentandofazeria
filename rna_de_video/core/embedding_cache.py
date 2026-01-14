from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from rna_de_video.core.config import AppConfig, embeddings_cache_dir


def _key_for_video(
    path: Path,
    *,
    mode: str,
    start_ms: int,
    end_ms: int,
    max_frames: int,
    min_step_s: float,
    image_size: int,
    backbone: str,
) -> str:
    try:
        st = path.stat()
        salt = f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}|{mode}|{start_ms}|{end_ms}|{max_frames}|{min_step_s}|{image_size}|{backbone}".encode(
            "utf-8"
        )
    except Exception:
        salt = f"{path.resolve()}|{mode}|{start_ms}|{end_ms}|{max_frames}|{min_step_s}|{image_size}|{backbone}".encode(
            "utf-8"
        )
    return hashlib.sha1(salt).hexdigest()


def embedding_path(config: AppConfig, *, mode: str, key: str) -> Path:
    safe_mode = "".join(ch for ch in str(mode) if ch.isalnum() or ch in {"-", "_"}) or "mode"
    return embeddings_cache_dir(config) / f"video_{safe_mode}_{key}.npy"


def load_embedding(config: AppConfig, key: str, *, mode: str = "appearance") -> np.ndarray | None:
    p = embedding_path(config, mode=mode, key=key)
    if not p.exists():
        return None
    try:
        return np.load(str(p)).astype(np.float32)
    except Exception:
        return None


def save_embedding(config: AppConfig, key: str, emb: np.ndarray, *, mode: str = "appearance") -> None:
    p = embedding_path(config, mode=mode, key=key)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(p), emb.astype(np.float32))


def get_or_compute_video_embedding(
    config: AppConfig,
    video_path: Path,
    *,
    mode: str,
    start_ms: int = -1,
    end_ms: int = -1,
    compute_fn,
) -> tuple[str, np.ndarray]:
    """Cache wrapper for a per-video embedding of a given mode.

    compute_fn() must return a normalized embedding np.ndarray.
    """

    key = _key_for_video(
        video_path,
        mode=str(mode),
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        max_frames=config.max_frames_per_video,
        min_step_s=config.min_frame_step_s,
        image_size=config.frame_resize,
        backbone=config.backbone,
    )

    cached = load_embedding(config, key, mode=str(mode))
    if cached is not None:
        return key, cached

    emb = compute_fn()
    if emb is None:
        raise ValueError("Embedding nulo.")
    save_embedding(config, key, emb, mode=str(mode))
    return key, emb
