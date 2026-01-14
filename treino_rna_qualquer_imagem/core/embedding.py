from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class EmbeddingBackendInfo:
    name: str
    pretrained: bool
    note: str


class EmbeddingExtractor:
    """Interface for embedding extraction."""

    def extract(self, image_path: Path) -> np.ndarray:
        raise NotImplementedError

    def info(self) -> EmbeddingBackendInfo:
        raise NotImplementedError


def _keras_model_cache_has(filename: str) -> bool:
    home = Path.home()
    # Default Keras cache path
    p = home / ".keras" / "models" / filename
    return p.exists()


class KerasResNet50Extractor(EmbeddingExtractor):
    """ResNet50 embeddings using Keras Applications.

    Offline behavior:
    - If cached weights exist locally, uses them.
    - Otherwise, runs with random weights (still functional but low quality).
    """

    def __init__(self, image_size: int = 224):
        self.image_size = image_size
        self._model = None
        self._pretrained = False

        # Import lazily.
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

    def extract(self, image_path: Path) -> np.ndarray:
        from PIL import Image

        img = Image.open(image_path).convert("RGB").resize((self.image_size, self.image_size))
        x = np.asarray(img, dtype=np.float32)
        x = np.expand_dims(x, axis=0)
        x = self._preprocess_input(x)
        emb = self._model(x, training=False).numpy().reshape(-1)
        # Normalize for cosine similarity usage.
        norm = np.linalg.norm(emb) + 1e-12
        return (emb / norm).astype(np.float32)


class SimpleHistogramExtractor(EmbeddingExtractor):
    """Fallback embedding extractor (no deep learning).

    This exists so the project can run even if TensorFlow is not installed.
    It does NOT meet the quality of a pretrained CNN.
    """

    def __init__(self, bins: int = 32, image_size: int = 224):
        self.bins = bins
        self.image_size = image_size

    def info(self) -> EmbeddingBackendInfo:
        return EmbeddingBackendInfo(
            "simple_histogram",
            False,
            "Fallback local (sem TensorFlow). Instale TensorFlow para EfficientNet/ResNet embeddings.",
        )

    def extract(self, image_path: Path) -> np.ndarray:
        from PIL import Image

        img = Image.open(image_path).convert("RGB").resize((self.image_size, self.image_size))
        x = np.asarray(img, dtype=np.uint8)
        feats = []
        for c in range(3):
            hist, _ = np.histogram(x[:, :, c], bins=self.bins, range=(0, 255), density=True)
            feats.append(hist.astype(np.float32))
        emb = np.concatenate(feats)
        norm = np.linalg.norm(emb) + 1e-12
        return (emb / norm).astype(np.float32)


def build_extractor(backbone: str, image_size: int) -> EmbeddingExtractor:
    """Create embedding extractor.

    Prefers Keras ResNet50 if TensorFlow is available; otherwise fallback.
    """

    try:
        if backbone.lower() in {"resnet50", "resnet"}:
            return KerasResNet50Extractor(image_size=image_size)
        # EfficientNet could be added similarly; keep ResNet50 as the main path.
        return KerasResNet50Extractor(image_size=image_size)
    except Exception:
        # TensorFlow not installed or other error
        return SimpleHistogramExtractor(image_size=image_size)
