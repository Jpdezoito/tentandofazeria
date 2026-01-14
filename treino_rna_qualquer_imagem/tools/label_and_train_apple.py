from __future__ import annotations

from pathlib import Path

from core.classifier import PrototypeClassifier
from core.config import AppConfig, dataset_db_path, thresholds_path
from core.dataset import add_image, connect, init_db, set_label
from core.embedding import build_extractor
from core.embedding_cache import get_or_compute_embedding, load_embedding
from core.thresholds import Thresholds, load_thresholds
from core.trainer import Trainer


def main() -> None:
    config = AppConfig()

    image_path = Path(__file__).resolve().parents[1] / "treinos" / "sample_images" / "maca.png"
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    conn = connect(dataset_db_path(config))
    init_db(conn)

    extractor = build_extractor(config.backbone, config.image_size)
    classifier = PrototypeClassifier()
    trainer = Trainer(config, classifier)
    trainer.try_load()

    thresholds = load_thresholds(
        thresholds_path(config),
        Thresholds(min_top1_confidence=config.min_top1_confidence, min_top1_similarity=config.min_top1_similarity),
    )

    key, emb = get_or_compute_embedding(config, extractor, image_path)
    rec = add_image(conn, path=image_path, embedding_key=key)

    label = "maçã"
    set_label(conn, rec.image_id, label)

    report = trainer.train_from_db(conn, embedding_loader=lambda k: load_embedding(config, k))

    pred = classifier.predict_open_world(
        emb,
        min_top1_confidence=thresholds.min_top1_confidence,
        min_top1_similarity=thresholds.min_top1_similarity,
        k=5,
    )

    print(f"Treino: classes={report.n_classes} rotuladas={report.n_labeled}")
    if pred.topk:
        print(f"Top1: {pred.topk[0].label} conf={pred.topk[0].confidence:.3f} sim={pred.topk[0].similarity:.3f} known={pred.known}")
    else:
        print(f"Sem predições. known={pred.known} reason={pred.reason}")


if __name__ == "__main__":
    main()
