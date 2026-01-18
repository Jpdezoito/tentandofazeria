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
from core.treino.importer import import_file  # noqa: E402


def _iter_training_files(cfg, extra: Path | None) -> list[Path]:
    files: list[Path] = []

    treinos_root = treinos_dir(cfg)
    import_root = import_dir(cfg)

    # Root-level training files (treinos/*.txt|*.jsonl|*.json)
    for p in sorted(treinos_root.iterdir()):
        if p.is_file() and p.suffix.lower() in {".txt", ".jsonl", ".json"}:
            files.append(p)

    # Import folder (treinos/importar/**)
    if import_root.exists():
        for p in sorted(import_root.glob("**/*")):
            if p.is_file() and p.suffix.lower() in {".txt", ".jsonl", ".json"}:
                files.append(p)

    # Code trainings (ia_treinos/codigo/importar/**)
    code_import = Path("../../ia_treinos/codigo/importar")
    if code_import.exists():
        for p in sorted(code_import.glob("**/*")):
            if p.is_file() and p.suffix.lower() in {".txt", ".jsonl", ".json", ".py"}:
                files.append(p)

    # Optional extra folder (ex: ia_treinos/conversa/importar)
    if extra and extra.exists():
        for p in sorted(extra.glob("**/*")):
            if p.is_file() and p.suffix.lower() in {".txt", ".jsonl", ".json"}:
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
    ap = argparse.ArgumentParser(description="RNA Conversa - Treino (importa dados)")
    ap.add_argument(
        "--extra",
        type=str,
        default="",
        help="Pasta extra para importar (ex.: ../ia_treinos/conversa/importar)",
    )
    ap.add_argument(
        "--save-as",
        type=str,
        default="",
        help="Salva o treino em treinos/modelo_treino/modelos_pre_treinados/<nome>",
    )
    ap.add_argument(
        "--activate",
        action="store_true",
        help="Ativa o modelo salvo via ATIVO.txt",
    )
    ap.add_argument(
        "--fresh",
        action="store_true",
        help="Não reaproveita o banco atual (somente arquivos de treino)",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve o destino do --save-as se já existir",
    )
    args = ap.parse_args(argv)

    cfg = config_from_env()
    extra = Path(args.extra).resolve() if args.extra else None

    save_as = args.save_as.strip()
    if save_as:
        dest_root = modelos_pre_treinados_dir(cfg) / save_as
        if dest_root.exists() and not args.overwrite:
            print(f"Destino já existe: {dest_root}. Use --overwrite para substituir.")
            return 2
        if dest_root.exists() and args.overwrite:
            shutil.rmtree(dest_root)
        dest_root.mkdir(parents=True, exist_ok=True)
        dest_db = dest_root / cfg.db_name
    else:
        dest_root = None
        dest_db = db_path(cfg)

    conn = connect(dest_db)
    init_db(conn)

    seeded = 0
    seen: set[tuple[str, str]] = set()
    if save_as and not args.fresh:
        seeded, seen = _seed_from_existing(conn, db_path(cfg))

    files = _iter_training_files(cfg, extra)
    if not files:
        print("Nenhum arquivo de treino encontrado.")
        return 1

    imported = 0
    errors: list[str] = []
    use_seen = seen if save_as else None
    for p in files:
        try:
            imported += import_file(conn, p, seen=use_seen)
        except Exception as e:
            errors.append(f"{p.name}: {e}")

    total = count_examples(conn)
    conn.close()

    if dest_root:
        _copy_settings(cfg, dest_root)
        if args.activate:
            marker = modelos_pre_treinados_dir(cfg) / "ATIVO.txt"
            marker.write_text(save_as, encoding="utf-8")

    if seeded:
        print(f"Base reaproveitada: {seeded} exemplo(s)")
    print(f"Arquivos lidos: {len(files)} | Importados: {imported} | Total no banco: {total}")
    if errors:
        print(f"Erros: {len(errors)}")
        for e in errors[:30]:
            print(f"ERRO: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
