from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


# Allow running as a file
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import config_from_env, db_path  # noqa: E402
from core.knowledge.store import init_db as init_knowledge_db  # noqa: E402
from core.memoria.long import init_db as init_long_memory_db  # noqa: E402
from core.memoria.store import connect, init_db  # noqa: E402
from core.runtime.orchestrator import ChatRuntime  # noqa: E402
from core.audio.stt_vosk import transcribe_wav_vosk  # noqa: E402


def _ffmpeg_exists() -> bool:
    from shutil import which

    return which("ffmpeg") is not None


def _convert_to_wav_mono_16k(src: Path, dst: Path) -> Path:
    if not _ffmpeg_exists():
        raise RuntimeError("ffmpeg não encontrado no PATH. Converta para WAV (mono 16k) ou instale ffmpeg.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "Falha ffmpeg").strip())
    return dst


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="RNA Conversa CLI (retorna JSON)")
    ap.add_argument("--text", default=None)
    ap.add_argument("--audio", default=None)
    ap.add_argument("--use-ollama", action="store_true")
    ap.add_argument("--model", default=None)
    args = ap.parse_args(argv)

    def emit_ok(payload: dict) -> None:
        out = {"ok": True, "tool": "conversa", "version": 1}
        out.update(payload)
        print(json.dumps(out, ensure_ascii=False))

    def emit_error(message: str, *, debug: str = "") -> None:
        out = {
            "ok": False,
            "tool": "conversa",
            "version": 1,
            "error": {"message": str(message)},
            "text": "",
            "engine": "",
            "debug": debug,
        }
        print(json.dumps(out, ensure_ascii=False))

    cfg = config_from_env()

    conn = connect(db_path(cfg))
    init_db(conn)
    init_knowledge_db(conn)
    init_long_memory_db(conn)
    runtime = ChatRuntime(cfg, conn)

    try:
        user_text = (args.text or "").strip() if args.text is not None else ""

        debug = ""
        if args.audio:
            src = Path(str(args.audio)).expanduser().resolve()
            if not src.exists() or not src.is_file():
                raise RuntimeError("Arquivo de áudio não encontrado")

            # Vosk needs WAV mono; convert if needed.
            wav = src
            if wav.suffix.lower() != ".wav":
                wav = (Path(db_path(cfg)).parent / "audio" / "cli_input.wav")
                wav = _convert_to_wav_mono_16k(src, wav)

            model_dir = Path(db_path(cfg)).parent / "vosk_model"
            tr = transcribe_wav_vosk(wav, model_dir=model_dir)
            user_text = (tr.text or "").strip()
            debug = "stt=vosk"
            if not user_text:
                emit_ok({"text": "(transcrição vazia)", "engine": "fallback", "debug": debug})
                return 0

        use_ollama = bool(args.use_ollama)
        model = (args.model or "").strip() or None

        res = runtime.reply(user_text, use_ollama=use_ollama, model=model)
        emit_ok({"text": res.text, "engine": res.engine, "debug": (debug + " " + res.debug).strip()})
        return 0
    except Exception as e:
        emit_error(str(e))
        return 2
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
