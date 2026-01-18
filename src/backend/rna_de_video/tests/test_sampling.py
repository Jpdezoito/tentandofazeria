from __future__ import annotations

from rna_de_video.core.video_frames import VideoInfo, sample_frame_indices


def test_sample_frame_indices_basic() -> None:
    info = VideoInfo(fps=30.0, frame_count=300, duration_s=10.0)
    idxs = sample_frame_indices(info, max_frames=16, min_step_s=0.75)
    assert len(idxs) <= 16
    assert all(0 <= i < 300 for i in idxs)
    assert idxs == sorted(set(idxs))


def test_sample_frame_indices_empty() -> None:
    info = VideoInfo(fps=0.0, frame_count=0, duration_s=0.0)
    idxs = sample_frame_indices(info, max_frames=16, min_step_s=0.75)
    assert idxs == []
