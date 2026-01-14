from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rna_de_conversa.core.config import config_from_env, db_path
from rna_de_conversa.core.knowledge.store import add_chunk, init_db as init_knowledge_db
from rna_de_conversa.core.memoria.store import connect, init_db


@dataclass(frozen=True)
class IndexResult:
    ok: bool
    source: str
    summary: str
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


def _format_topk(topk: list[dict[str, Any]], limit: int = 5) -> str:
    parts: list[str] = []
    for item in topk[:limit]:
        label = item.get("label")
        conf = float(item.get("confidence") or 0.0)
        sim = float(item.get("similarity") or 0.0)
        parts.append(f"{label} (conf={conf:.3f}, sim={sim:.3f})")
    return "; ".join(parts)


def _store_knowledge(source: str, text: str) -> None:
    cfg = config_from_env()
    conn = connect(db_path(cfg))
    init_db(conn)
    init_knowledge_db(conn)
    try:
        add_chunk(conn, source, text, meta_json="")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def index_image(image_path: Path, *, tool_root: Path) -> IndexResult:
    tool = tool_root / "tools" / "cli_classify.py"
    data = _run_json([sys.executable, str(tool), "--image", str(image_path)], cwd=tool_root)
    known = bool(data.get("known"))
    reason = str(data.get("reason") or "")
    topk = data.get("topk") or []
    summary = f"Imagem: {'conhecida' if known else 'desconhecida'} ({reason}). Top: {_format_topk(topk)}"
    src = f"image:{image_path}"
    _store_knowledge(src, summary)
    return IndexResult(ok=True, source=src, summary=summary, data=data)


def index_video(video_path: Path, *, tool_root: Path, mode: str = "appearance") -> IndexResult:
    tool = tool_root / "tools" / "cli_classify.py"
    data = _run_json(
        [sys.executable, str(tool), "--video", str(video_path), "--mode", str(mode)],
        cwd=tool_root,
    )
    known = bool(data.get("known"))
    reason = str(data.get("reason") or "")
    topk = data.get("topk") or []
    summary = f"Video: {'conhecido' if known else 'desconhecido'} ({reason}). Top: {_format_topk(topk)}"
    src = f"video:{video_path}"
    _store_knowledge(src, summary)
    return IndexResult(ok=True, source=src, summary=summary, data=data)
