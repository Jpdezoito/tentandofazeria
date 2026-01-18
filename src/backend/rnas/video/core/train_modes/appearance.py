from __future__ import annotations

import numpy as np

from rna_de_video.core.embedding import aggregate_frame_embeddings
from rna_de_video.core.train_modes.base import ModeComputeResult


class AppearanceMode:
    mode_id = "appearance"
    display_name = "Aparência (frames)"

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
        frame_embs: list[np.ndarray] = []
        for rgb in frames_rgb:
            frame_embs.append(appearance_extractor.extract_from_rgb(rgb))
        emb = aggregate_frame_embeddings(frame_embs)
        if emb is None:
            raise ValueError("Falha ao agregar embeddings de frames.")
        preview = frames_rgb[0]
        return ModeComputeResult(embedding=emb, preview_rgb=preview, n_frames=len(frames_rgb))
