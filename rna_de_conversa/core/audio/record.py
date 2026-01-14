from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WavRecording:
    path: Path
    sample_rate: int


def list_audio_devices() -> str:
    """Lista devices de áudio para debug (não levanta exceção)."""
    try:
        import sounddevice as sd  # type: ignore[import-not-found]
    except Exception:
        return "sounddevice não está instalado neste ambiente."

    try:
        devices = sd.query_devices()
        default_in, default_out = sd.default.device
    except Exception as e:
        return f"Falha ao consultar devices via sounddevice: {e}"

    lines: list[str] = [f"Default input={default_in}, output={default_out}"]
    for i, d in enumerate(devices):
        lines.append(
            f"[{i}] {d.get('name')} | in={d.get('max_input_channels')} out={d.get('max_output_channels')} | hostapi={d.get('hostapi')}"
        )
    return "\n".join(lines)


def record_wav_to_file(
    out_path: Path,
    *,
    seconds: float = 4.0,
    sample_rate: int = 16000,
    channels: int = 1,
    device: int | str | None = None,
) -> WavRecording:
    """Record microphone audio to a WAV file.

    Uses sounddevice (optional). If missing, raises RuntimeError with instructions.

    IMPORTANT: se você chamar isso a partir da UI (Tkinter), rode em thread separada,
    porque sd.wait() bloqueia.
    """
    try:
        import numpy as np  # type: ignore[import-not-found]
        import sounddevice as sd  # type: ignore[import-not-found]
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Para gravar áudio, instale sounddevice e numpy NO MESMO Python do VS Code:\n"
            "  python -m pip install sounddevice numpy\n"
            "Se estiver em Python 3.14 e não houver wheel, use Python 3.11/3.12."
        ) from e

    sec = float(seconds)
    if sec <= 0:
        raise ValueError("seconds deve ser > 0")
    sr = int(sample_rate)
    ch = int(channels)
    if sr <= 0:
        raise ValueError("sample_rate deve ser > 0")
    if ch <= 0:
        raise ValueError("channels deve ser > 0")

    frames = int(sec * sr)

    try:
        audio = sd.rec(
            frames,
            samplerate=sr,
            channels=ch,
            dtype="int16",
            device=device,
        )
        sd.wait()
    except Exception as e:
        try:
            sd.stop()
        except Exception:
            pass

        raise RuntimeError(
            "Falha ao gravar do microfone via sounddevice.\n"
            f"Parâmetros: seconds={sec}, sample_rate={sr}, channels={ch}, device={device}\n\n"
            "Devices disponíveis:\n"
            f"{list_audio_devices()}\n\n"
            "Dica: tente device=<índice> (ex.: device=1) ou verifique permissão de microfone no Windows."
        ) from e

    audio = np.asarray(audio)
    if audio.dtype != np.int16:
        audio = audio.astype(np.int16, copy=False)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(ch)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())

    return WavRecording(path=out_path, sample_rate=sr)
