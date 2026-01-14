from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelEntry:
    name: str
    task: str
    data_version: str
    path: str
    metrics: dict[str, Any]
    created_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {"models": []}
    try:
        return json.loads(index_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"models": []}


def register_model(index_path: Path, entry: ModelEntry) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_index(index_path)
    models = list(data.get("models") or [])
    models.append(
        {
            "name": entry.name,
            "task": entry.task,
            "data_version": entry.data_version,
            "path": entry.path,
            "metrics": entry.metrics,
            "created_at": entry.created_at or utc_now_iso(),
        }
    )
    data["models"] = models
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
