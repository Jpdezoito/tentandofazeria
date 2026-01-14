from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path


# Allow running as a file
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import AppConfig, aliases_path, index_db_path, stats_path  # noqa: E402
from core.index_db import connect, init_db  # noqa: E402
from core.normalize import normalize_text  # noqa: E402
from core.quick_search import QuickSearchParams, quick_search  # noqa: E402
from core.search import SearchParams, search  # noqa: E402
from core.storage import PreferenceStore  # noqa: E402


def _result_to_dict(r) -> dict:
    return {
        "path": str(r.path),
        "kind": str(getattr(r.kind, "value", r.kind)),
        "score": float(getattr(r, "score", 0.0)),
        "reason": str(getattr(r, "reason", "")),
        "source": str(getattr(r, "source", "")),
        "display_name": str(getattr(r, "display_name", "")),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="BuscarPastas CLI (retorna JSON)")
    ap.add_argument("--query", required=True)
    args = ap.parse_args(argv)

    q = (args.query or "").strip()
    if not q:
        print(json.dumps({"results": []}, ensure_ascii=False))
        return 0

    config = AppConfig()
    store = PreferenceStore(aliases_path=aliases_path(config), stats_path=stats_path(config))
    store.ensure_files()

    conn = connect(index_db_path(config))
    init_db(conn)
    try:
        qn = normalize_text(q)

        # Layer 1: quick search
        quick = quick_search(store, config, QuickSearchParams(query_text=q, query_norm=qn, action="open"))
        if quick:
            out = {"results": [_result_to_dict(r) for r in quick]}
            print(json.dumps(out, ensure_ascii=False))
            return 0

        # Layer 2: indexed search (if index exists)
        cancel = threading.Event()
        hits = search(conn, store, config, SearchParams(query_text=q, query_norm=qn, action="open"), cancel)
        out = {"results": [_result_to_dict(r) for r in hits]}
        print(json.dumps(out, ensure_ascii=False))
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
