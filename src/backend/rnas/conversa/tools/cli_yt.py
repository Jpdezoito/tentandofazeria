from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow running as a file
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.audio.stt_vosk import transcribe_wav_vosk  # noqa: E402
from core.config import config_from_env, treinos_dir  # noqa: E402


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def _get_meta(url: str) -> tuple[str, str]:
    cmd = ["yt-dlp", "--skip-download", "--print", "%(id)s\t%(title)s", url]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "Falha yt-dlp").strip())
    line = (proc.stdout or "").strip().splitlines()[0]
    if "\t" in line:
        vid, title = line.split("\t", 1)
    else:
        vid, title = "video", line
    return (vid.strip() or "video", title.strip() or "video")


def _download_audio(url: str, out_dir: Path, vid: str) -> Path:
    out_tpl = str(out_dir / f"{vid}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f",
        "bestaudio",
        "--extract-audio",
        "--audio-format",
        "wav",
        "--audio-quality",
        "0",
        "-o",
        out_tpl,
        url,
    ]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "Falha yt-dlp").strip())
    wav = out_dir / f"{vid}.wav"
    if not wav.exists():
        raise RuntimeError("Nao achei o audio WAV gerado.")
    
    # Converter para mono se necessário
    mono_wav = out_dir / f"{vid}_mono.wav"
    cmd_mono = [
        "ffmpeg",
        "-y",
        "-i",
        str(wav),
        "-ac",
        "1",
        str(mono_wav),
    ]
    proc_mono = _run(cmd_mono)
    if proc_mono.returncode == 0 and mono_wav.exists():
        wav.unlink()  # Remove o original
        wav = mono_wav
    # Se falhar, usa o original (pode não ser mono)
    
    return wav


def _make_thumbnail(video_path: Path, out_path: Path) -> Path | None:
    if not video_path.exists():
        return None
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        "00:00:01",
        "-i",
        str(video_path),
        "-vframes",
        "1",
        "-q:v",
        "3",
        str(out_path),
    ]
    proc = _run(cmd)
    if proc.returncode != 0:
        return None
    return out_path if out_path.exists() else None


def _simple_summary(text: str, max_sentences: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    out: list[str] = []
    for p in parts:
        s = p.strip()
        if not s:
            continue
        out.append(s)
        if len(out) >= max_sentences:
            break
    return " ".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="YouTube -> audio -> transcricao/treino")
    ap.add_argument("--url", required=True)
    ap.add_argument("--out-dir", default="", help="Pasta de saida (padrao: treinos/youtube)")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--video-only", action="store_true")
    ap.add_argument("--transcribe", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--summary-sentences", type=int, default=8)
    args = ap.parse_args(argv)

    cfg = config_from_env()
    base = treinos_dir(cfg)
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (base / "youtube")
    out_dir.mkdir(parents=True, exist_ok=True)

    vid, title = _get_meta(args.url)
    wav_path = _download_audio(args.url, out_dir, vid)

    result: dict[str, str] = {"id": vid, "title": title, "wav": str(wav_path)}

    if args.video or args.video_only:
        out_tpl = str(out_dir / f"{vid}.%(ext)s")
        cmd = [
            "yt-dlp",
            "-f",
            "bv*+ba/best",
            "--merge-output-format",
            "mp4",
            "-o",
            out_tpl,
            args.url,
        ]
        proc = _run(cmd)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Falha yt-dlp").strip())
        mp4 = out_dir / f"{vid}.mp4"
        if mp4.exists():
            result["video"] = str(mp4)
            thumb = _make_thumbnail(mp4, out_dir / f"{vid}_thumb.jpg")
            if thumb:
                result["thumbnail"] = str(thumb)

    if args.video_only:
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        return 0

    transcript = ""
    if args.transcribe or args.summarize or args.train:
        model_dir = base / "vosk_model"
        # Copy model to temp dir to avoid encoding issues
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_model_dir = Path(temp_dir) / "model"
            shutil.copytree(model_dir, temp_model_dir)
            tr = transcribe_wav_vosk(wav_path, model_dir=temp_model_dir)
        transcript = (tr.text or "").strip()
        t_path = out_dir / f"{vid}_transcript.txt"
        t_path.write_text(transcript, encoding="utf-8")
        result["transcript"] = str(t_path)

    summary = ""
    if args.summarize or args.train:
        summary = _simple_summary(transcript, max_sentences=int(args.summary_sentences))
        s_path = out_dir / f"{vid}_summary.txt"
        s_path.write_text(summary, encoding="utf-8")
        result["summary"] = str(s_path)

    if args.train:
        import_dir = base / "importar"
        import_dir.mkdir(parents=True, exist_ok=True)
        jl_path = import_dir / f"yt_{vid}.jsonl"
        lines = []
        if summary:
            lines.append(
                json.dumps(
                    {"instruction": f"Resuma o video: {title}", "input": "", "output": summary},
                    ensure_ascii=False,
                )
            )
        if transcript:
            lines.append(
                json.dumps(
                    {"instruction": f"Transcreva o video: {title}", "input": "", "output": transcript},
                    ensure_ascii=False,
                )
            )
        jl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result["train_jsonl"] = str(jl_path)

    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
