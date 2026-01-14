from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppPaths:
    root: Path
    conversa: Path
    buscarpastas: Path
    qualquer_imagem: Path
    video: Path
    treinos: Path
    data: Path
    models: Path
    eval_dir: Path
    logs: Path


def default_paths(root: Path) -> AppPaths:
    return AppPaths(
        root=root,
        conversa=root / "rna_de_conversa",
        buscarpastas=root / "treino_rna_buscarpastas",
        qualquer_imagem=root / "treino_rna_qualquer_imagem",
        video=root / "rna_de_video",
        treinos=root / "ia_treinos",
        data=root / "data",
        models=root / "models",
        eval_dir=root / "eval",
        logs=root / "logs",
    )


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def resolve_paths(root: Path, config_path: Path) -> AppPaths:
    cfg = load_config(config_path)
    defaults = default_paths(root)

    def _pick(name: str, fallback: Path) -> Path:
        raw = str(cfg.get("paths", {}).get(name, "")).strip()
        if not raw:
            return fallback
        p = Path(raw)
        return p if p.is_absolute() else (root / p)

    return AppPaths(
        root=root,
        conversa=_pick("conversa", defaults.conversa),
        buscarpastas=_pick("buscarpastas", defaults.buscarpastas),
        qualquer_imagem=_pick("qualquer_imagem", defaults.qualquer_imagem),
        video=_pick("video", defaults.video),
        treinos=_pick("treinos", defaults.treinos),
        data=_pick("data", defaults.data),
        models=_pick("models", defaults.models),
        eval_dir=_pick("eval", defaults.eval_dir),
        logs=_pick("logs", defaults.logs),
    )
