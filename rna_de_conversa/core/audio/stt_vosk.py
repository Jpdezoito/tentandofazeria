from __future__ import annotations

import importlib
import json
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Transcription:
    text: str


def transcribe_wav_vosk(wav_path: Path, model_dir: Path) -> Transcription:
    """Offline STT using Vosk.

    Requires vosk (pip install vosk) and a Vosk model folder.
    """
    try:
        vosk = importlib.import_module("vosk")
        KaldiRecognizer = getattr(vosk, "KaldiRecognizer")
        Model = getattr(vosk, "Model")
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Para transcrever áudio offline, instale vosk: pip install vosk"
        ) from e

    if not model_dir.exists():
        raise RuntimeError(
            "Modelo Vosk não encontrado. Coloque um modelo em: "
            f"{model_dir} (ex.: vosk-model-small-pt-0.3)"
        )

    wf = wave.open(str(wav_path), "rb")
    if wf.getnchannels() != 1:
        raise RuntimeError("Vosk requer WAV mono (1 canal).")

    model = Model(str(model_dir))
    rec = KaldiRecognizer(model, wf.getframerate())

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        rec.AcceptWaveform(data)

    res = json.loads(rec.FinalResult())
    text = (res.get("text") or "").strip()
    return Transcription(text=text)

