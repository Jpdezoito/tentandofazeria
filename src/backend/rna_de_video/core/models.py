from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


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
class VideoRecord:
    video_id: int
    path: Path
    added_at: datetime
    label: Optional[str]
    embedding_key: str
    n_frames: int
    duration_s: float


@dataclass(frozen=True)
class ClusterSummary:
    cluster_id: str
    count: int
    name: Optional[str]
