from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SubprocessResult:
    ok: bool
    data: dict[str, Any] | None
    error: str | None
    raw: str


def _run_json_cmd(args: list[str], *, cwd: Path) -> SubprocessResult:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except Exception as e:
        return SubprocessResult(ok=False, data=None, error=str(e), raw="")

    raw = (proc.stdout or "").strip()
    if proc.returncode != 0:
        err = (proc.stderr or raw or f"exit={proc.returncode}").strip()
        return SubprocessResult(ok=False, data=None, error=err, raw=raw)

    try:
        data = json.loads(raw) if raw else {}
        if isinstance(data, dict):
            return SubprocessResult(ok=True, data=data, error=None, raw=raw)
        return SubprocessResult(ok=False, data=None, error="Resposta JSON inválida (não é objeto)", raw=raw)
    except Exception as e:
        return SubprocessResult(ok=False, data=None, error=f"Falha ao ler JSON: {e}", raw=raw)


class RnaConversaClient:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.script = _pick_first_existing(
            [
                project_root / "rnas" / "conversa" / "tools" / "cli_chat.py",
                project_root / "backend" / "rnas" / "conversa" / "tools" / "cli_chat.py",
                project_root / "rna_de_conversa" / "tools" / "cli_chat.py",
            ]
        )
        self.yt_script = _pick_first_existing(
            [
                project_root / "rnas" / "conversa" / "tools" / "cli_yt.py",
                project_root / "backend" / "rnas" / "conversa" / "tools" / "cli_yt.py",
                project_root / "rna_de_conversa" / "tools" / "cli_yt.py",
            ]
        )
        self.cwd = _pick_first_existing_dir(
            [
                project_root / "rnas" / "conversa",
                self.script.parents[1],
                project_root / "rna_de_conversa",
                project_root,
            ]
        )

    def reply(self, text: str, *, use_ollama: bool, model: str | None) -> SubprocessResult:
        args = [sys.executable, str(self.script), "--text", text]
        if use_ollama:
            args.append("--use-ollama")
        if model:
            args += ["--model", model]
        return _run_json_cmd(args, cwd=self.cwd)

    def reply_with_image(self, text: str, image_path: Path, *, use_ollama: bool, model: str | None) -> SubprocessResult:
        args = [sys.executable, str(self.script), "--text", text, "--image", str(image_path)]
        if use_ollama:
            args.append("--use-ollama")
        if model:
            args += ["--model", model]
        return _run_json_cmd(args, cwd=self.cwd)

    def youtube(self, url: str, *, video_only: bool = False) -> SubprocessResult:
        args = [
            sys.executable,
            str(self.yt_script),
            "--url",
            url,
            "--video",
            "--transcribe",
            "--summarize",
            "--train",
        ]
        if video_only:
            args = [
                sys.executable,
                str(self.yt_script),
                "--url",
                url,
                "--video-only",
            ]
        return _run_json_cmd(args, cwd=self.cwd)


class BuscarPastasClient:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.script = _pick_first_existing(
            [
                project_root / "rnas" / "buscarpastas" / "tools" / "cli_search.py",
                project_root / "backend" / "rnas" / "buscarpastas" / "tools" / "cli_search.py",
                project_root / "treino_rna_buscarpastas" / "tools" / "cli_search.py",
            ]
        )
        self.cwd = _pick_first_existing_dir(
            [
                project_root / "rnas" / "buscarpastas",
                self.script.parents[1],
                project_root / "treino_rna_buscarpastas",
                project_root,
            ]
        )

    def search(self, query: str) -> SubprocessResult:
        args = [sys.executable, str(self.script), "--query", query]
        return _run_json_cmd(args, cwd=self.cwd)


class QualquerImagemClient:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.script = _pick_first_existing(
            [
                project_root / "rnas" / "imagem" / "tools" / "cli_classify.py",
                project_root / "backend" / "rnas" / "imagem" / "tools" / "cli_classify.py",
                project_root / "treino_rna_qualquer_imagem" / "tools" / "cli_classify.py",
            ]
        )
        self.cwd = _pick_first_existing_dir(
            [
                project_root / "rnas" / "imagem",
                self.script.parents[1],
                project_root / "treino_rna_qualquer_imagem",
                project_root,
            ]
        )

    def classify(self, image_path: Path) -> SubprocessResult:
        args = [sys.executable, str(self.script), "--image", str(image_path)]
        return _run_json_cmd(args, cwd=self.cwd)


class RnaVideoClient:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.script = _pick_first_existing(
            [
                project_root / "rnas" / "video" / "tools" / "cli_classify.py",
                project_root / "backend" / "rnas" / "video" / "tools" / "cli_classify.py",
                project_root / "rna_de_video" / "tools" / "cli_classify.py",
            ]
        )
        self.cwd = _pick_first_existing_dir(
            [
                project_root / "rnas" / "video",
                self.script.parents[1],
                project_root / "rna_de_video",
                project_root,
            ]
        )

    def classify(
        self,
        video_ref: str,
        *,
        mode: str,
        start_s: float | None = None,
        end_s: float | None = None,
    ) -> SubprocessResult:
        args = [sys.executable, str(self.script), "--video", str(video_ref), "--mode", str(mode)]
        if start_s is not None or end_s is not None:
            if start_s is None or end_s is None:
                # Let CLI validate too, but keep friendly error here.
                return SubprocessResult(ok=False, data=None, error="Informe start e end (segundos).", raw="")
            args += ["--start", str(float(start_s)), "--end", str(float(end_s))]
        return _run_json_cmd(args, cwd=self.cwd)


def _pick_first_existing(candidates: list[Path]) -> Path:
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _pick_first_existing_dir(candidates: list[Path]) -> Path:
    for p in candidates:
        if p.exists() and p.is_dir():
            return p
    return candidates[0]


class RnaCodigoClient:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.script = _pick_first_existing(
            [
                project_root / "backend" / "rnas" / "codigo" / "tools" / "cli_code.py",
            ]
        )
        self.cwd = _pick_first_existing_dir(
            [
                project_root / "backend" / "rnas" / "codigo",
            ]
        )

    def generate_code(self, prompt: str, *, max_length: int = 200) -> SubprocessResult:
        args = [sys.executable, str(self.script), "--prompt", prompt, "--max-length", str(max_length)]
        return _run_json_cmd(args, cwd=self.cwd)
