from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from rna_de_video.core.models import PredictResult, Prediction


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    e = np.exp(x)
    return e / (np.sum(e) + 1e-12)


@dataclass
class ClassifierState:
    labels: list[str]
    centroids: dict[str, list[float]]


class PrototypeClassifier:
    """Classifier based on per-class centroids (cosine similarity).

    This is robust for incremental learning: you can add new classes anytime.
    """

    def __init__(self) -> None:
        self._centroids: dict[str, np.ndarray] = {}

    @property
    def labels(self) -> list[str]:
        return sorted(self._centroids.keys())

    def update_centroids(self, label_to_embeddings: dict[str, np.ndarray]) -> None:
        new: dict[str, np.ndarray] = {}
        for label, embs in label_to_embeddings.items():
            if embs.size == 0:
                continue
            c = np.mean(embs, axis=0)
            c = c / (np.linalg.norm(c) + 1e-12)
            new[label] = c.astype(np.float32)
        self._centroids = new

    def predict_topk(self, emb: np.ndarray, k: int = 5) -> list[Prediction]:
        if not self._centroids:
            return []

        labels = list(self._centroids.keys())
        C = np.stack([self._centroids[l] for l in labels], axis=0)
        sims = (C @ emb.reshape(-1, 1)).reshape(-1)

        probs = _softmax(sims * 12.0)
        order = np.argsort(-probs)

        out: list[Prediction] = []
        for idx in order[:k]:
            i = int(idx)
            out.append(Prediction(label=labels[i], confidence=float(probs[i]), similarity=float(sims[i])))
        return out

    def predict_open_world(self, emb: np.ndarray, *, min_top1_confidence: float, min_top1_similarity: float, k: int = 5) -> PredictResult:
        topk = self.predict_topk(emb, k=k)
        if not topk:
            return PredictResult(known=False, topk=[], reason="sem classes ainda")

        top1 = topk[0]
        if top1.confidence < min_top1_confidence:
            return PredictResult(known=False, topk=topk, reason="confiança baixa")
        if top1.similarity < min_top1_similarity:
            return PredictResult(known=False, topk=topk, reason="similaridade baixa")
        return PredictResult(known=True, topk=topk, reason="ok")

    def save(self, path: Path) -> None:
        data = {"labels": self.labels, "centroids": {k: v.tolist() for k, v in self._centroids.items()}}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: Path) -> None:
        if not path.exists():
            self._centroids = {}
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        cents: dict[str, np.ndarray] = {}
        for label, vec in (data.get("centroids") or {}).items():
            arr = np.asarray(vec, dtype=np.float32)
            n = np.linalg.norm(arr) + 1e-12
            cents[str(label)] = (arr / n).astype(np.float32)
        self._centroids = cents
