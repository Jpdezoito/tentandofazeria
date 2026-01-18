from __future__ import annotations

import numpy as np

from rna_de_video.core.audio_from_video import audio_embedding_simple, extract_mono_wav_from_video
from rna_de_video.core.train_modes.base import ModeComputeResult


class AudioMode:
    mode_id = "audio"
    display_name = "Áudio (ffmpeg)"

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
        res = extract_mono_wav_from_video(
            video_path,
            sample_rate=16000,
            start_ms=start_ms,
            end_ms=end_ms,
            max_seconds=60.0,
        )
        emb = audio_embedding_simple(res.samples, res.sample_rate, max_bins=64)
        preview = frames_rgb[0] if frames_rgb else np.zeros((10, 10, 3), dtype=np.uint8)
        return ModeComputeResult(embedding=emb, preview_rgb=preview, n_frames=len(frames_rgb))
