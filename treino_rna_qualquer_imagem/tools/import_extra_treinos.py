from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.classifier import PrototypeClassifier
from core.config import AppConfig, dataset_db_path
from core.dataset import add_image, connect, init_db, set_label
from core.embedding import build_extractor
from core.embedding_cache import get_or_compute_embedding
from core.image_sources import resolve_image_reference_to_file


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@dataclass(frozen=True)
class ImportReport:
    imported: int
    skipped_existing: int
    errors: int


def iter_labeled_files(images_root: Path) -> Iterable[tuple[str, Path]]:
    if not images_root.exists():
        return
    for label_dir in sorted([p for p in images_root.iterdir() if p.is_dir()]):
        label = label_dir.name.strip()
        if not label:
            continue
        for p in sorted(label_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in _IMAGE_EXTS:
                yield (label, p)


def iter_csv_refs(csv_path: Path) -> Iterable[tuple[str, str]]:
    if not csv_path.exists():
        return

    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|") if sample.strip() else csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            if not row:
                continue
            label = (row.get("label") or row.get("rotulo") or "").strip()
            ref = (row.get("ref") or row.get("url") or row.get("path") or "").strip()
            if label and ref:
                yield (label, ref)


def import_extras(extra_dir: Path, *, config: Optional[AppConfig] = None) -> ImportReport:
    cfg = config or AppConfig()

    images_root = extra_dir / "imagens"
    csv_refs = extra_dir / "enderecos.csv"

    conn = connect(dataset_db_path(cfg))
    init_db(conn)

    extractor = build_extractor(cfg.backbone, cfg.image_size)

    imported = 0
    skipped = 0
    errors = 0

    def ingest(label: str, file_path: Path) -> None:
        nonlocal imported, skipped, errors
        try:
            key, _emb = get_or_compute_embedding(cfg, extractor, file_path)
            rec = add_image(conn, path=file_path, embedding_key=key)
            set_label(conn, rec.image_id, label)
            imported += 1
        except Exception as e:
            msg = str(e)
            if "UNIQUE" in msg or "unique" in msg:
                skipped += 1
            else:
                errors += 1
                print(f"ERRO: {label} | {file_path} | {e}")

    for label, p in iter_labeled_files(images_root):
        ingest(label, p)

    for label, ref in iter_csv_refs(csv_refs):
        try:
            p = resolve_image_reference_to_file(cfg, ref)
            ingest(label, p)
        except Exception as e:
            errors += 1
            print(f"ERRO: {label} | {ref} | {e}")

    conn.close()
    return ImportReport(imported=imported, skipped_existing=skipped, errors=errors)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", type=str, required=True, help="Pasta ia_treinos")
    args = ap.parse_args()

    extra = Path(args.extra).resolve()
    extra.mkdir(parents=True, exist_ok=True)

    # Ensure classifier files can still load later
    _ = PrototypeClassifier()

    rep = import_extras(extra)
    print(f"Importados={rep.imported} | duplicados/ignorados={rep.skipped_existing} | erros={rep.errors}")


if __name__ == "__main__":
    main()
