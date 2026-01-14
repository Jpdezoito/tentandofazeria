from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class VideoInfo:
    fps: float
    frame_count: int
    duration_s: float


def _require_cv2():
    try:
        import cv2  # type: ignore

        return cv2
    except Exception as e:
        raise RuntimeError(
            "opencv-python não está instalado. Rode: pip install opencv-python (ou use imageio+ffmpeg)."
        ) from e


def _try_cv2():
    try:
        import cv2  # type: ignore

        return cv2
    except Exception:
        return None


def _require_imageio_v2():
    try:
        import imageio.v2 as iio  # type: ignore

        return iio
    except Exception as e:
        raise RuntimeError(
            "Não consegui importar imageio. Rode: pip install imageio imageio-ffmpeg"
        ) from e


def probe_video(path: Path) -> VideoInfo:
    cv2 = _try_cv2()
    if cv2 is not None:
        cap = cv2.VideoCapture(str(path))
        try:
            if not cap.isOpened():
                raise ValueError("Não consegui abrir o vídeo (codec/arquivo).")
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration_s = float(frame_count / fps) if fps > 1e-6 else 0.0
            return VideoInfo(fps=fps, frame_count=frame_count, duration_s=duration_s)
        finally:
            cap.release()

    iio = _require_imageio_v2()
    reader = iio.get_reader(str(path), format="ffmpeg")
    try:
        meta = reader.get_meta_data() or {}
        fps = float(meta.get("fps") or 0.0)
        duration_s = float(meta.get("duration") or 0.0)
        frame_count = int(meta.get("nframes") or 0)
        if frame_count <= 0 and duration_s > 0 and fps > 1e-6:
            frame_count = int(duration_s * fps)
        if duration_s <= 0 and frame_count > 0 and fps > 1e-6:
            duration_s = float(frame_count / fps)
        return VideoInfo(fps=fps, frame_count=frame_count, duration_s=duration_s)
    finally:
        try:
            reader.close()
        except Exception:
            pass


def sample_frame_indices(info: VideoInfo, *, max_frames: int, min_step_s: float) -> list[int]:
    if info.frame_count <= 0:
        return []

    max_frames = max(1, int(max_frames))
    if info.fps > 1e-6:
        min_step_frames = int(max(1.0, min_step_s * info.fps))
    else:
        min_step_frames = 1

    # Greedy sampling with minimum step.
    idxs: list[int] = []
    i = 0
    while i < info.frame_count and len(idxs) < max_frames:
        idxs.append(int(i))
        i += min_step_frames

    if len(idxs) < max_frames and info.frame_count > 0:
        # Fill remaining evenly spaced across the full range.
        targets = np.linspace(0, max(0, info.frame_count - 1), num=max_frames, dtype=int).tolist()
        merged = sorted(set(idxs + [int(t) for t in targets]))
        # Keep earliest max_frames for determinism
        return merged[:max_frames]

    return idxs


def read_frames_rgb(path: Path, indices: list[int]) -> list[np.ndarray]:
    """Read specific frame indices and return RGB uint8 arrays (H,W,3)."""

    if not indices:
        return []

    cv2 = _try_cv2()
    if cv2 is not None:
        cap = cv2.VideoCapture(str(path))
        try:
            if not cap.isOpened():
                raise ValueError("Não consegui abrir o vídeo (codec/arquivo).")

            frames: list[np.ndarray] = []
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    continue
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                frames.append(rgb)
            return frames
        finally:
            cap.release()

    iio = _require_imageio_v2()
    reader = iio.get_reader(str(path), format="ffmpeg")
    try:
        frames: list[np.ndarray] = []
        for idx in indices:
            try:
                rgb = reader.get_data(int(idx))
            except Exception:
                continue
            if rgb is None:
                continue
            arr = np.asarray(rgb)
            if arr.ndim == 2:
                arr = np.stack([arr, arr, arr], axis=-1)
            if arr.ndim != 3 or arr.shape[-1] < 3:
                continue
            arr = arr[:, :, :3]
            if arr.dtype != np.uint8:
                arr = np.clip(arr, 0, 255).astype(np.uint8)
            frames.append(arr)
        return frames
    finally:
        try:
            reader.close()
        except Exception:
            pass
