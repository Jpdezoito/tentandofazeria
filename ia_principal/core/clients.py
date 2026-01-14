from __future__ import annotations

import json
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
        self.script = project_root / "rna_de_conversa" / "tools" / "cli_chat.py"

    def reply(self, text: str, *, use_ollama: bool, model: str | None) -> SubprocessResult:
        args = [sys.executable, str(self.script), "--text", text]
        if use_ollama:
            args.append("--use-ollama")
        if model:
            args += ["--model", model]
        return _run_json_cmd(args, cwd=self.project_root / "rna_de_conversa")


class BuscarPastasClient:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.script = project_root / "treino_rna_buscarpastas" / "tools" / "cli_search.py"

    def search(self, query: str) -> SubprocessResult:
        args = [sys.executable, str(self.script), "--query", query]
        return _run_json_cmd(args, cwd=self.project_root / "treino_rna_buscarpastas")


class QualquerImagemClient:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.script = project_root / "treino_rna_qualquer_imagem" / "tools" / "cli_classify.py"

    def classify(self, image_path: Path) -> SubprocessResult:
        args = [sys.executable, str(self.script), "--image", str(image_path)]
        return _run_json_cmd(args, cwd=self.project_root / "treino_rna_qualquer_imagem")


class RnaVideoClient:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.script = project_root / "rna_de_video" / "tools" / "cli_classify.py"

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
        return _run_json_cmd(args, cwd=self.project_root / "rna_de_video")
