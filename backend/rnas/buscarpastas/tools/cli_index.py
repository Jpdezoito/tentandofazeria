from __future__ import annotations

import argparse
import sys
import threading
from dataclasses import replace
from pathlib import Path

# Allow running as a file
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import config_from_env, index_db_path  # noqa: E402
from core.index_db import connect, init_db, item_count  # noqa: E402
from core.indexer import index_all  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="BuscarPastas CLI - indexacao completa")
    ap.add_argument("--no-drive", action="store_true", help="Nao varre drives completos (C:, D:, ...)")
    ap.add_argument("--max-drive-seconds", type=float, default=None, help="Limite de tempo por drive (segundos)")
    ap.add_argument("--root", action="append", default=[], help="Indexa apenas este caminho (pode repetir)")
    args = ap.parse_args()

    config = config_from_env()
    if args.no_drive:
        config = replace(config, enable_drive_scan=False)
    if args.max_drive_seconds is not None:
        config = replace(config, max_drive_scan_seconds=float(args.max_drive_seconds))

    conn = connect(index_db_path(config))
    init_db(conn)

    cancel = threading.Event()
    if args.root:
        from core.indexer import index_root  # noqa: E402
        from core.windows_paths import SearchRoot  # noqa: E402

        for raw in args.root:
            root_path = Path(raw).expanduser().resolve()
            if not root_path.exists():
                print(f"Raiz nao encontrada: {root_path}")
                continue
            root = SearchRoot(f"root_{root_path.name}", root_path)
            index_root(conn, config, root, cancel_event=cancel, log=print)
    else:
        index_all(conn, config, cancel_event=cancel, log=print)

    total = item_count(conn)
    conn.close()
    print(f"Indexacao finalizada. Itens no indice: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
