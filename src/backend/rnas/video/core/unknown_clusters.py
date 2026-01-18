from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ClusterAssign:
    cluster_id: str
    similarity: float


class UnknownClusterer:
    """Simple online clustering for unknown items.

    Keeps centroid per cluster in memory; caller persists cluster_id in DB.
    """

    def __init__(self, threshold: float = 0.55):
        self.threshold = float(threshold)
        self._centroids: dict[str, np.ndarray] = {}

    def assign(self, emb: np.ndarray) -> ClusterAssign:
        if not self._centroids:
            cid = self._new_cluster_id(emb)
            self._centroids[cid] = emb
            return ClusterAssign(cluster_id=cid, similarity=1.0)

        best_id = None
        best_sim = -1.0
        for cid, c in self._centroids.items():
            sim = float(c @ emb)
            if sim > best_sim:
                best_sim = sim
                best_id = cid

        if best_id is None or best_sim < self.threshold:
            cid = self._new_cluster_id(emb)
            self._centroids[cid] = emb
            return ClusterAssign(cluster_id=cid, similarity=float(best_sim))

        # Update centroid with a running average (small step).
        c = self._centroids[best_id]
        new_c = c * 0.8 + emb * 0.2
        new_c = new_c / (np.linalg.norm(new_c) + 1e-12)
        self._centroids[best_id] = new_c.astype(np.float32)
        return ClusterAssign(cluster_id=str(best_id), similarity=float(best_sim))

    def _new_cluster_id(self, emb: np.ndarray) -> str:
        h = hashlib.sha1(emb.tobytes()).hexdigest()[:10]
        return f"cluster_{h}"
