from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Thresholds:
    min_top1_confidence: float
    min_top1_similarity: float


def load_thresholds(path: Path, defaults: Thresholds) -> Thresholds:
    if not path.exists():
        save_thresholds(path, defaults)
        return defaults
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return Thresholds(
            min_top1_confidence=float(obj.get("min_top1_confidence", defaults.min_top1_confidence)),
            min_top1_similarity=float(obj.get("min_top1_similarity", defaults.min_top1_similarity)),
        )
    except Exception:
        return defaults


def save_thresholds(path: Path, thr: Thresholds) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"min_top1_confidence": thr.min_top1_confidence, "min_top1_similarity": thr.min_top1_similarity}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
