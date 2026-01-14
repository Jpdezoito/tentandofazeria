from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# Allow running as a file
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.classifier import PrototypeClassifier  # noqa: E402
from core.config import AppConfig, config_from_env, model_dir, thresholds_path  # noqa: E402
from core.embedding import build_extractor  # noqa: E402
from core.embedding_cache import get_or_compute_embedding  # noqa: E402
from core.thresholds import Thresholds, load_thresholds  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="QualquerImagem CLI (retorna JSON)")
    ap.add_argument("--image", required=True)
    args = ap.parse_args(argv)

    def emit_ok(payload: dict) -> None:
        out = {"ok": True, "tool": "qualquer_imagem", "version": 1}
        out.update(payload)
        print(json.dumps(out, ensure_ascii=False))

    def emit_error(message: str) -> None:
        out = {
            "ok": False,
            "tool": "qualquer_imagem",
            "version": 1,
            "error": {"message": str(message)},
            "known": False,
            "reason": "error",
            "topk": [],
        }
        print(json.dumps(out, ensure_ascii=False))

    try:
        image_path = Path(str(args.image)).expanduser().resolve()
        if not image_path.exists() or not image_path.is_file():
            raise FileNotFoundError("Arquivo de imagem não encontrado")

        config = config_from_env()

        extractor = build_extractor(config.backbone, config.image_size)
        _, emb = get_or_compute_embedding(config, extractor, image_path)

        clf = PrototypeClassifier()
        clf.load(model_dir(config) / "centroids.json")

        t = load_thresholds(
            thresholds_path(config),
            defaults=Thresholds(
                min_top1_confidence=config.min_top1_confidence,
                min_top1_similarity=config.min_top1_similarity,
            ),
        )

        pred = clf.predict_open_world(
            emb,
            min_top1_confidence=float(t.min_top1_confidence),
            min_top1_similarity=float(t.min_top1_similarity),
            k=5,
        )

        emit_ok(
            {
                "known": bool(pred.known),
                "reason": str(pred.reason),
                "topk": [
                    {"label": p.label, "confidence": float(p.confidence), "similarity": float(p.similarity)}
                    for p in (pred.topk or [])
                ],
            }
        )
        return 0
    except Exception as e:
        emit_error(str(e))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
