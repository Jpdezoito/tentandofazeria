from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core.classifier import PrototypeClassifier
from core.config import AppConfig, model_dir
from core.dataset import list_labeled

LogFn = Callable[[str], None]


@dataclass(frozen=True)
class TrainReport:
    n_labeled: int
    n_classes: int


class Trainer:
    """Training orchestration using a replay buffer strategy.

    For simplicity and robustness, we train centroids from a bounded replay set.
    """

    def __init__(self, config: AppConfig, classifier: PrototypeClassifier):
        self.config = config
        self.classifier = classifier

    def train_from_db(self, conn, embedding_loader: Callable[[str], np.ndarray | None], log: Optional[LogFn] = None) -> TrainReport:
        labeled = list_labeled(conn)
        if log:
            log(f"Treino: {len(labeled)} imagem(ns) rotulada(s)")

        # Build replay buffer capped per class.
        per_class: dict[str, list[np.ndarray]] = {}
        for rec in labeled:
            if not rec.label:
                continue
            emb = embedding_loader(rec.embedding_key)
            if emb is None:
                continue
            per_class.setdefault(rec.label, []).append(emb)

        sampled: dict[str, np.ndarray] = {}
        for label, embs in per_class.items():
            if len(embs) > self.config.replay_per_class:
                embs = random.sample(embs, self.config.replay_per_class)
            sampled[label] = np.stack(embs, axis=0)

        self.classifier.update_centroids(sampled)

        # Save checkpoint
        state_path = model_dir(self.config) / "centroids.json"
        self.classifier.save(state_path)

        if log:
            log(f"Treino OK: classes={len(sampled)} | salvo em {state_path}")

        return TrainReport(n_labeled=len(labeled), n_classes=len(sampled))

    def try_load(self) -> None:
        state_path = model_dir(self.config) / "centroids.json"
        self.classifier.load(state_path)
