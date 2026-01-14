from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class EmbeddingBackendInfo:
    name: str
    pretrained: bool
    note: str


class EmbeddingExtractor:
    def extract_from_rgb(self, rgb_uint8: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def info(self) -> EmbeddingBackendInfo:
        raise NotImplementedError


def _keras_model_cache_has(filename: str) -> bool:
    from pathlib import Path

    p = Path.home() / ".keras" / "models" / filename
    return p.exists()


class KerasResNet50Extractor(EmbeddingExtractor):
    def __init__(self, image_size: int = 224):
        self.image_size = int(image_size)
        self._model = None
        self._pretrained = False

        import tensorflow as tf  # type: ignore
        from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input  # type: ignore

        self._tf = tf
        self._preprocess_input = preprocess_input

        weight_file = "resnet50_weights_tf_dim_ordering_tf_kernels_notop.h5"
        use_pretrained = _keras_model_cache_has(weight_file)
        weights = "imagenet" if use_pretrained else None
        self._pretrained = bool(use_pretrained)
        self._model = ResNet50(include_top=False, weights=weights, pooling="avg")

    def info(self) -> EmbeddingBackendInfo:
        if self._pretrained:
            return EmbeddingBackendInfo("keras_resnet50", True, "Pesos pré-treinados encontrados no cache local.")
        return EmbeddingBackendInfo(
            "keras_resnet50",
            False,
            "Pesos pré-treinados NÃO encontrados localmente; usando pesos aleatórios (qualidade baixa).",
        )

    def extract_from_rgb(self, rgb_uint8: np.ndarray) -> np.ndarray:
        # rgb_uint8: (H,W,3) uint8
        from PIL import Image

        img = Image.fromarray(rgb_uint8.astype(np.uint8), mode="RGB").resize((self.image_size, self.image_size))
        x = np.asarray(img, dtype=np.float32)
        x = np.expand_dims(x, axis=0)
        x = self._preprocess_input(x)
        emb = self._model(x, training=False).numpy().reshape(-1)
        norm = np.linalg.norm(emb) + 1e-12
        return (emb / norm).astype(np.float32)


class SimpleHistogramExtractor(EmbeddingExtractor):
    def __init__(self, bins: int = 32, image_size: int = 224):
        self.bins = int(bins)
        self.image_size = int(image_size)

    def info(self) -> EmbeddingBackendInfo:
        return EmbeddingBackendInfo(
            "simple_histogram",
            False,
            "Fallback local (sem TensorFlow). Para embeddings melhores, instale TensorFlow e use ResNet50.",
        )

    def extract_from_rgb(self, rgb_uint8: np.ndarray) -> np.ndarray:
        from PIL import Image

        img = Image.fromarray(rgb_uint8.astype(np.uint8), mode="RGB").resize((self.image_size, self.image_size))
        x = np.asarray(img, dtype=np.uint8)
        feats = []
        for c in range(3):
            hist, _ = np.histogram(x[:, :, c], bins=self.bins, range=(0, 255), density=True)
            feats.append(hist.astype(np.float32))
        emb = np.concatenate(feats)
        norm = np.linalg.norm(emb) + 1e-12
        return (emb / norm).astype(np.float32)


def build_extractor(backbone: str, image_size: int) -> EmbeddingExtractor:
    b = (backbone or "").lower().strip()

    if b in {"fallback", "hist", "fallback_hist", "simple_histogram"}:
        return SimpleHistogramExtractor(image_size=image_size)

    try:
        return KerasResNet50Extractor(image_size=image_size)
    except Exception:
        return SimpleHistogramExtractor(image_size=image_size)


def aggregate_frame_embeddings(frame_embs: list[np.ndarray]) -> Optional[np.ndarray]:
    if not frame_embs:
        return None
    E = np.stack(frame_embs, axis=0)
    v = np.mean(E, axis=0)
    n = np.linalg.norm(v) + 1e-12
    return (v / n).astype(np.float32)
