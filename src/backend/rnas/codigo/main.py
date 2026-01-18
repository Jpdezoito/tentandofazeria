from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import (  # noqa: E402
    config_from_env,
    db_path,
    import_dir,
    modelos_pre_treinados_dir,
    settings_path,
    treinos_dir,
)
from core.memoria.store import add_example, connect, count_examples, init_db, iter_all  # noqa: E402
from core.models import CodeModel  # noqa: E402
from core.treino.importer import import_file  # noqa: E402


def _iter_training_files(cfg, extra: Path | None) -> list[Path]:
    files: list[Path] = []

    treinos_root = treinos_dir(cfg)
    import_root = import_dir(cfg)

    # Root-level training files (treinos/*.txt|*.jsonl|*.json)
    for p in sorted(treinos_root.iterdir()):
        if p.is_file() and p.suffix.lower() in {".txt", ".jsonl", ".json", ".py"}:
            files.append(p)

    # Import folder (treinos/importar/**)
    if import_root.exists():
        for p in sorted(import_root.glob("**/*")):
            if p.is_file() and p.suffix.lower() in {".txt", ".jsonl", ".json", ".py"}:
                files.append(p)

    # Optional extra folder (ex: ia_treinos/codigo/importar)
    if extra and extra.exists():
        for p in sorted(extra.glob("**/*")):
            if p.is_file() and p.suffix.lower() in {".txt", ".jsonl", ".json", ".py"}:
                files.append(p)

    # Remove duplicates preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in files:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        unique.append(p)
    return unique


def _seed_from_existing(conn_new, src_db: Path) -> tuple[int, set[tuple[str, str]]]:
    if not src_db.exists():
        return (0, set())

    conn_old = connect(src_db)
    init_db(conn_old)

    seen: set[tuple[str, str]] = set()
    imported = 0
    for ex in iter_all(conn_old):
        key = (ex.user_text.strip(), ex.assistant_text.strip())
        if key in seen:
            continue
        add_example(conn_new, ex.user_text, ex.assistant_text)
        seen.add(key)
        imported += 1

    conn_old.close()
    return (imported, seen)


def _copy_settings(cfg, dest_root: Path) -> None:
    src = settings_path(cfg)
    if not src.exists():
        return
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_root / cfg.settings_name)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="RNA Código - Treino (importa dados de programação)")
    ap.add_argument(
        "--extra",
        type=str,
        default="",
        help="Pasta extra para importar (ex.: ../ia_treinos/codigo/importar)",
    )
    ap.add_argument(
        "--save-as",
        type=str,
        default="",
        help="Salva o treino em treinos/modelo_treino/modelos_pre_treinados/<nome>",
    )
    ap.add_argument(
        "--seed-from",
        type=str,
        default="",
        help="Semeia o banco de dados com exemplos de outro treino (caminho para db)",
    )
    ap.add_argument(
        "--count-only",
        action="store_true",
        help="Apenas conta os exemplos e sai",
    )
    ap.add_argument(
        "--train",
        action="store_true",
        help="Treina o modelo com os dados importados",
    )
    args = ap.parse_args(argv)

    cfg = config_from_env()

    # Conectar ao banco
    conn = connect(db_path(cfg))
    init_db(conn)

    # Semear com dados existentes se solicitado
    if args.seed_from:
        src_db = Path(args.seed_from).expanduser().resolve()
        imported, seen = _seed_from_existing(conn, src_db)
        print(f"Semeado com {imported} exemplos de {src_db}")

    # Arquivos de treino
    extra = Path(args.extra).expanduser().resolve() if args.extra else None
    training_files = _iter_training_files(cfg, extra)

    if args.count_only:
        total = count_examples(conn)
        print(f"Total de exemplos no banco: {total}")
        conn.close()
        return 0

    # Importar arquivos
    imported = 0
    for file_path in training_files:
        try:
            n = import_file(conn, file_path)
            imported += n
            print(f"Importado {n} exemplos de {file_path}")
        except Exception as e:
            print(f"Erro ao importar {file_path}: {e}")

    total = count_examples(conn)
    print(f"Total de exemplos: {total} (importados agora: {imported})")

    # Treinar modelo se solicitado
    if args.train:
        print("Coletando textos de treinamento...")
        train_texts = [ex.assistant_text for ex in iter_all(conn)]
        if not train_texts:
            print("Nenhum exemplo encontrado para treinamento.")
            conn.close()
            return 1
        print(f"Treinando com {len(train_texts)} exemplos...")

        model = CodeModel(cfg)
        output_dir = modelos_pre_treinados_dir(cfg) / "codigo_treinado"
        model.train(train_texts, output_dir)
        print(f"Modelo treinado e salvo em {output_dir}")

    # Salvar modelo se solicitado
    if args.save_as:
        dest_root = modelos_pre_treinados_dir(cfg) / args.save_as
        dest_root.mkdir(parents=True, exist_ok=True)
        dest_db = dest_root / "memoria.db"
        shutil.copy2(db_path(cfg), dest_db)
        _copy_settings(cfg, dest_root)
        print(f"Modelo salvo em {dest_root}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())