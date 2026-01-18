from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class UnknownClusterer:
    """Very simple incremental clustering for unknown embeddings.

    - Maintains centroids for provisional clusters.
    - Assigns by cosine similarity threshold; otherwise creates a new cluster.

    This is the local fallback when you don't want heavy dependencies.
    """

    threshold: float
    centroids: dict[str, np.ndarray]

    def __init__(self, threshold: float):
        self.threshold = float(threshold)
        self.centroids = {}

    def _new_id(self) -> str:
        n = len(self.centroids) + 1
        return f"Classe_Nova_{n:03d}"

    def assign(self, emb: np.ndarray) -> str:
        if not self.centroids:
            cid = self._new_id()
            self.centroids[cid] = emb.astype(np.float32)
            return cid

        best_id: Optional[str] = None
        best_sim = -1.0
        for cid, c in self.centroids.items():
            sim = float(c @ emb)
            if sim > best_sim:
                best_sim = sim
                best_id = cid

        if best_id is None or best_sim < self.threshold:
            cid = self._new_id()
            self.centroids[cid] = emb.astype(np.float32)
            return cid

        # Update centroid with a moving average
        c = self.centroids[best_id]
        new = 0.9 * c + 0.1 * emb
        new = new / (np.linalg.norm(new) + 1e-12)
        self.centroids[best_id] = new.astype(np.float32)
        return best_id
