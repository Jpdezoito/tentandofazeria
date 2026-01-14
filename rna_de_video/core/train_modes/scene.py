from __future__ import annotations

import numpy as np

from rna_de_video.core.embedding import aggregate_frame_embeddings
from rna_de_video.core.train_modes.base import ModeComputeResult


def _mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    da = a.astype(np.int16)
    db = b.astype(np.int16)
    return float(np.mean(np.abs(db - da)))


def _select_keyframes(frames_rgb: list[np.ndarray], *, max_keyframes: int = 8, diff_threshold: float = 18.0) -> list[np.ndarray]:
    """Pick keyframes based on simple scene-change heuristic.

    Works on already-sampled frames.
    """

    if not frames_rgb:
        return []

    max_keyframes = max(1, int(max_keyframes))

    # Downscale for diff computation
    def down(x: np.ndarray) -> np.ndarray:
        # nearest-neighbor subsample to ~64px width/height
        h, w = x.shape[0], x.shape[1]
        step_h = max(1, h // 64)
        step_w = max(1, w // 64)
        return x[::step_h, ::step_w, :]

    downs = [down(f) for f in frames_rgb]

    selected: list[np.ndarray] = [frames_rgb[0]]
    last = downs[0]

    for i in range(1, len(frames_rgb)):
        if len(selected) >= max_keyframes:
            break
        d = _mean_abs_diff(last, downs[i])
        if d >= diff_threshold:
            selected.append(frames_rgb[i])
            last = downs[i]

    if len(selected) == 1 and len(frames_rgb) >= 2:
        # Ensure at least 2 frames when available
        selected.append(frames_rgb[-1])

    return selected


class SceneMode:
    mode_id = "scene"
    display_name = "Cena (chave + aparência)"

    def compute(
        self,
        *,
        video_path,
        frames_rgb: list[np.ndarray],
        appearance_extractor,
        config,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> ModeComputeResult:
        if not frames_rgb:
            raise ValueError("Sem frames.")

        keyframes = _select_keyframes(frames_rgb, max_keyframes=8, diff_threshold=18.0)
        if not keyframes:
            raise ValueError("Falha ao selecionar keyframes.")

        frame_embs: list[np.ndarray] = []
        for rgb in keyframes:
            frame_embs.append(appearance_extractor.extract_from_rgb(rgb))

        emb = aggregate_frame_embeddings(frame_embs)
        if emb is None:
            raise ValueError("Falha ao agregar embeddings.")

        return ModeComputeResult(embedding=emb, preview_rgb=keyframes[0], n_frames=len(keyframes))
