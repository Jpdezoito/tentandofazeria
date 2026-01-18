from __future__ import annotations

import numpy as np

from rna_de_video.core.train_modes.base import ModeComputeResult


def _motion_hist(frames_rgb: list[np.ndarray], *, bins: int = 16) -> np.ndarray:
    if len(frames_rgb) < 2:
        raise ValueError("Preciso de pelo menos 2 frames para extrair movimento.")

    feats: list[np.ndarray] = []
    for a, b in zip(frames_rgb[:-1], frames_rgb[1:]):
        da = a.astype(np.int16)
        db = b.astype(np.int16)
        diff = np.abs(db - da).astype(np.uint8)  # (H,W,3)
        hists = []
        for c in range(3):
            hist, _ = np.histogram(diff[:, :, c], bins=bins, range=(0, 255), density=True)
            hists.append(hist.astype(np.float32))
        feats.append(np.concatenate(hists, axis=0))

    v = np.mean(np.stack(feats, axis=0), axis=0)
    n = np.linalg.norm(v) + 1e-12
    return (v / n).astype(np.float32)


class MotionMode:
    mode_id = "motion"
    display_name = "Movimento (diferença)"

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
        emb = _motion_hist(frames_rgb, bins=16)
        preview = frames_rgb[0] if frames_rgb else np.zeros((10, 10, 3), dtype=np.uint8)
        return ModeComputeResult(embedding=emb, preview_rgb=preview, n_frames=len(frames_rgb))
