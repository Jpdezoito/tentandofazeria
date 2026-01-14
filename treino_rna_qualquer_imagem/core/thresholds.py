from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Thresholds:
    min_top1_confidence: float
    min_top1_similarity: float


def load_thresholds(path: Path, defaults: Thresholds) -> Thresholds:
    if not path.exists():
        save_thresholds(path, defaults)
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Thresholds(
            min_top1_confidence=float(data.get("min_top1_confidence", defaults.min_top1_confidence)),
            min_top1_similarity=float(data.get("min_top1_similarity", defaults.min_top1_similarity)),
        )
    except Exception:
        save_thresholds(path, defaults)
        return defaults


def save_thresholds(path: Path, t: Thresholds) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(t), ensure_ascii=False, indent=2), encoding="utf-8")
