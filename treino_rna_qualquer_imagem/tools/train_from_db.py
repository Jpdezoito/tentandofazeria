from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.classifier import PrototypeClassifier
from core.config import AppConfig, dataset_db_path
from core.dataset import connect, init_db
from core.embedding_cache import load_embedding
from core.trainer import Trainer


def main() -> None:
    cfg = AppConfig()
    conn = connect(dataset_db_path(cfg))
    init_db(conn)

    classifier = PrototypeClassifier()
    trainer = Trainer(cfg, classifier)
    trainer.try_load()

    report = trainer.train_from_db(conn, embedding_loader=lambda k: load_embedding(cfg, k), log=print)
    conn.close()

    print(f"Treino final: classes={report.n_classes} | rotuladas={report.n_labeled}")


if __name__ == "__main__":
    main()
