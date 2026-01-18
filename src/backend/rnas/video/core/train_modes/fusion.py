from __future__ import annotations

import numpy as np

from rna_de_video.core.embedding import aggregate_frame_embeddings
from rna_de_video.core.train_modes.base import ModeComputeResult
from rna_de_video.core.train_modes.motion import _motion_hist


class FusionMode:
    mode_id = "fusion"
    display_name = "Aparência + Movimento"

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

        # Appearance
        frame_embs: list[np.ndarray] = []
        for rgb in frames_rgb:
            frame_embs.append(appearance_extractor.extract_from_rgb(rgb))
        a = aggregate_frame_embeddings(frame_embs)
        if a is None:
            raise ValueError("Falha ao agregar embeddings de frames.")

        # Motion
        m = _motion_hist(frames_rgb, bins=16)

        v = np.concatenate([a.astype(np.float32), m.astype(np.float32)], axis=0)
        n = np.linalg.norm(v) + 1e-12
        v = (v / n).astype(np.float32)
        return ModeComputeResult(embedding=v, preview_rgb=frames_rgb[0], n_frames=len(frames_rgb))
