from __future__ import annotations

import io
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class AudioExtractResult:
    samples: np.ndarray  # float32 mono [-1,1]
    sample_rate: int


def _require_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError(
            "ffmpeg não encontrado no PATH. Instale o ffmpeg (recomendado) para usar o modo Áudio."
        )
    return exe


def extract_mono_wav_from_video(
    video_path: Path,
    *,
    sample_rate: int = 16000,
    start_ms: int | None = None,
    end_ms: int | None = None,
    max_seconds: float = 60.0,
) -> AudioExtractResult:
    """Extract mono WAV from a video using ffmpeg and return samples.

    Uses stdout piping (no temp files).
    """

    ffmpeg = _require_ffmpeg()

    args: list[str] = [ffmpeg, "-hide_banner", "-loglevel", "error"]

    # Segment selection
    if start_ms is not None and start_ms >= 0:
        args += ["-ss", f"{start_ms / 1000.0:.3f}"]

    args += ["-i", str(video_path)]

    if end_ms is not None and start_ms is not None and end_ms > start_ms:
        dur = (end_ms - start_ms) / 1000.0
        dur = min(dur, float(max_seconds))
        args += ["-t", f"{dur:.3f}"]
    else:
        args += ["-t", f"{float(max_seconds):.3f}"]

    args += [
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(int(sample_rate)),
        "-f",
        "wav",
        "pipe:1",
    ]

    cp = subprocess.run(args, capture_output=True)
    if cp.returncode != 0:
        err = (cp.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg falhou ao extrair áudio: {err or 'erro desconhecido'}")

    raw = cp.stdout or b""
    if not raw:
        raise RuntimeError("Áudio vazio (sem faixa de áudio ou falha na extração).")

    with wave.open(io.BytesIO(raw), "rb") as wf:
        n_channels = wf.getnchannels()
        sr = int(wf.getframerate())
        n_frames = int(wf.getnframes())
        sampwidth = int(wf.getsampwidth())
        pcm = wf.readframes(n_frames)

    if n_channels != 1:
        raise RuntimeError("Extração retornou áudio não-mono (inesperado).")

    # Convert PCM to float32
    if sampwidth == 2:
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        x = np.frombuffer(pcm, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise RuntimeError(f"Formato WAV não suportado (sampwidth={sampwidth}).")

    if x.size == 0:
        raise RuntimeError("Áudio extraído veio vazio.")

    x = np.clip(x, -1.0, 1.0).astype(np.float32)
    return AudioExtractResult(samples=x, sample_rate=sr)


def audio_embedding_simple(
    samples: np.ndarray,
    sample_rate: int,
    *,
    max_bins: int = 64,
) -> np.ndarray:
    """Compute a small fixed-size embedding from audio.

    Features:
    - downsampled energy envelope
    - summary stats of energy and spectral centroid

    Returns L2-normalized float32 vector.
    """

    x = samples.astype(np.float32)
    sr = int(sample_rate)

    # Window: 0.25s
    win = max(256, int(0.25 * sr))
    hop = win

    # Energy envelope
    energies: list[float] = []
    centroids: list[float] = []

    for start in range(0, max(0, x.size - win + 1), hop):
        seg = x[start : start + win]
        e = float(np.mean(seg * seg))
        energies.append(e)

        # Spectral centroid
        spec = np.fft.rfft(seg * np.hanning(seg.size))
        mag = np.abs(spec).astype(np.float32)
        freqs = np.fft.rfftfreq(seg.size, d=1.0 / sr).astype(np.float32)
        denom = float(np.sum(mag) + 1e-12)
        c = float(np.sum(freqs * mag) / denom)
        centroids.append(c)

    if not energies:
        energies = [float(np.mean(x * x))]
        centroids = [0.0]

    e_arr = np.asarray(energies, dtype=np.float32)
    c_arr = np.asarray(centroids, dtype=np.float32)

    # Normalize centroid to 0..1 by Nyquist
    nyq = max(1.0, sr / 2.0)
    c_arr = np.clip(c_arr / float(nyq), 0.0, 1.0)

    # Downsample energy envelope to fixed bins
    if e_arr.size == 1:
        env = np.full((max_bins,), float(e_arr[0]), dtype=np.float32)
    else:
        idx = np.linspace(0, e_arr.size - 1, num=max_bins)
        env = np.interp(idx, np.arange(e_arr.size), e_arr).astype(np.float32)

    # Stats
    def stats(v: np.ndarray) -> np.ndarray:
        v = v.astype(np.float32)
        return np.asarray(
            [
                float(np.mean(v)),
                float(np.std(v)),
                float(np.min(v)),
                float(np.max(v)),
                float(np.quantile(v, 0.25)),
                float(np.quantile(v, 0.50)),
                float(np.quantile(v, 0.75)),
            ],
            dtype=np.float32,
        )

    feat = np.concatenate([env, stats(e_arr), stats(c_arr)], axis=0).astype(np.float32)
    n = float(np.linalg.norm(feat) + 1e-12)
    return (feat / n).astype(np.float32)
