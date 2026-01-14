from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ia_core.config import AppPaths, load_config
from ia_core.safety import is_action_allowed, is_allowed_path, is_safe_mode


@dataclass(frozen=True)
class AssistantReply:
    text: str
    kind: str
    data: dict[str, Any]


def _run_json(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or raw or f"exit={proc.returncode}").strip())
    if not raw:
        return {}
    return json.loads(raw)


def _allowed_roots_from_config(config_path: Path) -> list[Path]:
    cfg = load_config(config_path)
    roots = cfg.get("safety", {}).get("allowed_roots", [])
    out: list[Path] = []
    for r in roots or []:
        p = Path(str(r))
        out.append(p)
    return out


def route_assistant(
    user_text: str,
    *,
    paths: AppPaths,
    config_path: Path,
    use_ollama: bool = False,
    model: str = "",
) -> AssistantReply:
    text = (user_text or "").strip()
    if not text:
        return AssistantReply(text="", kind="empty", data={})

    safe_mode = is_safe_mode(config_path=config_path)
    allowed_roots = _allowed_roots_from_config(config_path) if safe_mode else []

    def _deny(action: str) -> AssistantReply:
        return AssistantReply(text="action_not_allowed", kind="error", data={"action": action})

    if text.lower().startswith("/buscar ") or text.lower().startswith("buscar:"):
        if not is_action_allowed("buscar", config_path=config_path):
            return _deny("buscar")
        q = text.split(" ", 1)[1] if " " in text else text.split(":", 1)[1]
        tool = paths.buscarpastas / "tools" / "cli_search.py"
        data = _run_json([sys.executable, str(tool), "--query", q.strip()], cwd=paths.buscarpastas)
        return AssistantReply(text="ok", kind="buscar", data=data)

    p = Path(text.strip("\"'"))
    if p.exists() and p.is_file():
        if safe_mode and not is_allowed_path(p, allowed_roots):
            return AssistantReply(text="path_not_allowed", kind="error", data={"path": str(p)})
        ext = p.suffix.lower()
        if ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}:
            if not is_action_allowed("imagem", config_path=config_path):
                return _deny("imagem")
            tool = paths.qualquer_imagem / "tools" / "cli_classify.py"
            data = _run_json([sys.executable, str(tool), "--image", str(p)], cwd=paths.qualquer_imagem)
            return AssistantReply(text="ok", kind="imagem", data=data)
        if ext in {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}:
            if not is_action_allowed("video", config_path=config_path):
                return _deny("video")
            tool = paths.video / "tools" / "cli_classify.py"
            data = _run_json([sys.executable, str(tool), "--video", str(p), "--mode", "appearance"], cwd=paths.video)
            return AssistantReply(text="ok", kind="video", data=data)
        if ext in {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}:
            if not is_action_allowed("audio", config_path=config_path):
                return _deny("audio")
            tool = paths.conversa / "tools" / "cli_chat.py"
            cmd = [sys.executable, str(tool), "--audio", str(p)]
            if use_ollama:
                cmd.append("--use-ollama")
            if model:
                cmd += ["--model", model]
            data = _run_json(cmd, cwd=paths.conversa)
            return AssistantReply(text="ok", kind="audio", data=data)

    if not is_action_allowed("chat", config_path=config_path):
        return _deny("chat")

    tool = paths.conversa / "tools" / "cli_chat.py"
    cmd = [sys.executable, str(tool), "--text", text]
    if use_ollama:
        cmd.append("--use-ollama")
    if model:
        cmd += ["--model", model]
    data = _run_json(cmd, cwd=paths.conversa)
    return AssistantReply(text="ok", kind="conversa", data=data)
