from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ImageRecord:
    image_id: int
    path: Path
    added_at: datetime
    label: Optional[str]
    cluster_id: Optional[str]
    embedding_key: str


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float
    similarity: float


@dataclass(frozen=True)
class PredictResult:
    known: bool
    topk: list[Prediction]
    reason: str


@dataclass(frozen=True)
class ClusterSummary:
    cluster_id: str
    count: int
    name: Optional[str] = None
