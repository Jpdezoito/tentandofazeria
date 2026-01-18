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

from core.config import config_from_env, db_path  # noqa: E402
from core.knowledge.chunking import ChunkConfig, chunk_text  # noqa: E402
from core.knowledge.ingest import (  # noqa: E402
    IngestStats,
    discover_files,
    load_documents,
    normalize_source_meta,
)
from core.knowledge.store import add_chunk, init_db as init_knowledge_db  # noqa: E402
from core.knowledge.vector_index import build_vector_index_from_db  # noqa: E402
from core.knowledge.vector_store import upsert_chunks  # noqa: E402
from core.memoria.long import init_db as init_long_memory_db  # noqa: E402
from core.memoria.store import connect, init_db  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingestao de arquivos para RAG (retorna JSON)")
    ap.add_argument("--path", required=True, help="Arquivo ou pasta para indexar")
    ap.add_argument("--max-files", type=int, default=0, help="Limitar numero de arquivos (0 = sem limite)")
    ap.add_argument("--chunk-tokens", type=int, default=0, help="Tokens por chunk (0 = padrao)")
    ap.add_argument("--chunk-overlap", type=int, default=0, help="Overlap por chunk (0 = padrao)")
    ap.add_argument("--no-index", action="store_true", help="Nao atualizar indice vetorial")
    args = ap.parse_args(argv)

    def emit_ok(payload: dict) -> None:
        out = {"ok": True, "tool": "ingest", "version": 1}
        out.update(payload)
        print(json.dumps(out, ensure_ascii=False))

    def emit_error(message: str) -> None:
        out = {"ok": False, "tool": "ingest", "version": 1, "error": {"message": str(message)}}
        print(json.dumps(out, ensure_ascii=False))

    cfg = config_from_env()

    conn = connect(db_path(cfg))
    init_db(conn)
    init_knowledge_db(conn)
    init_long_memory_db(conn)

    target = Path(str(args.path)).expanduser().resolve()
    files = discover_files(target)
    if args.max_files and args.max_files > 0:
        files = files[: int(args.max_files)]

    chunk_cfg = ChunkConfig(
        max_tokens=int(args.chunk_tokens or cfg.knowledge_chunk_tokens),
        overlap=int(args.chunk_overlap or cfg.knowledge_chunk_overlap),
    )

    stats = IngestStats()
    errors: list[str] = []
    new_chunks = []

    for fp in files:
        stats = IngestStats(
            files=stats.files + 1,
            documents=stats.documents,
            chunks=stats.chunks,
            skipped=stats.skipped,
        )
        try:
            docs = list(load_documents(fp))
        except Exception as e:
            errors.append(f"{fp}: {e}")
            stats = IngestStats(
                files=stats.files,
                documents=stats.documents,
                chunks=stats.chunks,
                skipped=stats.skipped + 1,
            )
            continue

        if not docs:
            stats = IngestStats(
                files=stats.files,
                documents=stats.documents,
                chunks=stats.chunks,
                skipped=stats.skipped + 1,
            )
            continue

        for doc in docs:
            chunks = chunk_text(doc.text, chunk_cfg)
            if not chunks:
                stats = IngestStats(
                    files=stats.files,
                    documents=stats.documents,
                    chunks=stats.chunks,
                    skipped=stats.skipped + 1,
                )
                continue

            stats = IngestStats(
                files=stats.files,
                documents=stats.documents + 1,
                chunks=stats.chunks,
                skipped=stats.skipped,
            )

            for idx, ch in enumerate(chunks):
                meta = normalize_source_meta(doc.source, {"chunk_index": idx})
                kc = add_chunk(conn, doc.source, ch, meta_json=meta)
                new_chunks.append(kc)
                stats = IngestStats(
                    files=stats.files,
                    documents=stats.documents,
                    chunks=stats.chunks + 1,
                    skipped=stats.skipped,
                )

    index_info: dict[str, str | bool] = {"ok": False}
    vector_store_info: dict[str, str | bool] = {"ok": False}
    if bool(cfg.knowledge_vector_backend) and str(cfg.knowledge_vector_backend).lower() == "chroma":
        try:
            st = upsert_chunks(cfg, new_chunks)
            vector_store_info = {"ok": st.ok, "backend": st.backend, "message": st.message}
        except Exception as e:
            vector_store_info = {"ok": False, "error": str(e)}
    if not args.no_index and bool(cfg.knowledge_build_index):
        try:
            idx_path = build_vector_index_from_db(cfg, conn)
            if idx_path:
                index_info = {"ok": True, "path": str(idx_path)}
            else:
                index_info = {"ok": False, "error": "Sem chunks para indexar"}
        except Exception as e:
            index_info = {"ok": False, "error": str(e)}

    emit_ok(
        {
            "stats": {
                "files": stats.files,
                "documents": stats.documents,
                "chunks": stats.chunks,
                "skipped": stats.skipped,
            },
            "errors": errors,
            "vector_index": index_info,
            "vector_store": vector_store_info,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
