from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from rna_de_video.core.classifier import PrototypeClassifier
from rna_de_video.core.config import AppConfig, model_dir
from rna_de_video.core.dataset import list_labeled_embedding_keys

LogFn = Callable[[str], None]


@dataclass(frozen=True)
class TrainReport:
    n_labeled: int
    n_classes: int


class Trainer:
    def __init__(self, config: AppConfig, classifier: PrototypeClassifier):
        self.config = config
        self.classifier = classifier

    def train_from_db(
        self,
        conn,
        *,
        mode: str,
        embedding_loader: Callable[[str], np.ndarray | None],
        log: Optional[LogFn] = None,
    ) -> TrainReport:
        pairs = list_labeled_embedding_keys(conn, mode=str(mode))
        if log:
            log(f"Treino[{mode}]: {len(pairs)} embedding(s) rotulado(s)")

        per_class: dict[str, list[np.ndarray]] = {}
        for label, key in pairs:
            emb = embedding_loader(key)
            if emb is None:
                continue
            per_class.setdefault(str(label), []).append(emb)

        sampled: dict[str, np.ndarray] = {}
        for label, embs in per_class.items():
            if len(embs) > self.config.replay_per_class:
                embs = random.sample(embs, self.config.replay_per_class)
            sampled[label] = np.stack(embs, axis=0)

        self.classifier.update_centroids(sampled)

        safe_mode = "".join(ch for ch in str(mode) if ch.isalnum() or ch in {"-", "_"}) or "mode"
        state_path = model_dir(self.config) / f"centroids_{safe_mode}.json"
        self.classifier.save(state_path)

        if log:
            log(f"Treino OK: classes={len(sampled)} | salvo em {state_path}")

        return TrainReport(n_labeled=len(pairs), n_classes=len(sampled))

        

    def try_load(self, *, mode: str) -> None:
        safe_mode = "".join(ch for ch in str(mode) if ch.isalnum() or ch in {"-", "_"}) or "mode"
        state_path = model_dir(self.config) / f"centroids_{safe_mode}.json"
        self.classifier.load(state_path)
