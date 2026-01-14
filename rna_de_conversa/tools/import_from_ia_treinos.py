from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from anywhere
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config import AppConfig, db_path
from core.memoria.store import connect, init_db
from core.treino.importer import import_folder


def resolve_source(extra_root: Path) -> Path:
    # Preferred layout:
    # ia_treinos/conversa/importar/*.txt|*.jsonl
    # Fallback:
    # ia_treinos/conversa/*.txt|*.jsonl
    base = extra_root / "conversa"
    if (base / "importar").exists():
        return base / "importar"
    return base


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--extra",
        type=str,
        default="",
        help="Pasta ia_treinos (default: ../ia_treinos relativo ao workspace)",
    )
    args = ap.parse_args()

    # Workspace root is parent of rna_de_conversa
    ws_root = _PROJECT_ROOT.parent
    extra_root = Path(args.extra).resolve() if args.extra else (ws_root / "ia_treinos").resolve()

    src = resolve_source(extra_root)
    if not src.exists():
        print(f"Nada para importar: {src} não existe.")
        return

    cfg = AppConfig()
    conn = connect(db_path(cfg))
    init_db(conn)

    imported, errors = import_folder(conn, src)
    conn.close()

    print(f"Importados={imported} | erros={len(errors)} | fonte={src}")
    for e in errors[:30]:
        print(f"ERRO: {e}")


if __name__ == "__main__":
    main()
