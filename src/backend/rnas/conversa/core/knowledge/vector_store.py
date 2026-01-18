from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.config import AppConfig, knowledge_chroma_dir
from core.models import KnowledgeChunk, RetrievedChunk


@dataclass(frozen=True)
class VectorStoreStatus:
    ok: bool
    backend: str
    message: str = ""


def _require_chroma():
    try:
        import importlib

        importlib.import_module("chromadb")
        importlib.import_module("chromadb.utils.embedding_functions")
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Dependencias para Chroma nao instaladas. "
            "Instale chromadb e sentence-transformers."
        ) from e


def _get_collection(cfg: AppConfig):
    _require_chroma()
    import importlib

    chromadb = importlib.import_module("chromadb")
    embedding_functions = importlib.import_module("chromadb.utils.embedding_functions")

    persist_dir = knowledge_chroma_dir(cfg)
    client = chromadb.PersistentClient(path=str(persist_dir))
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=str(cfg.knowledge_embedding_model)
    )
    return client.get_or_create_collection(
        name=str(cfg.knowledge_chroma_collection),
        embedding_function=ef,
    )


def upsert_chunks(cfg: AppConfig, chunks: Iterable[KnowledgeChunk]) -> VectorStoreStatus:
    try:
        col = _get_collection(cfg)
    except Exception as e:
        return VectorStoreStatus(ok=False, backend="chroma", message=str(e))

    ids: list[str] = []
    docs: list[str] = []
    metadatas: list[dict] = []

    for ch in chunks:
        text = (ch.text or "").strip()
        if not text:
            continue
        ids.append(str(ch.chunk_id))
        docs.append(text)
        metadatas.append(
            {
                "source": ch.source,
                "chunk_id": int(ch.chunk_id),
                "meta_json": ch.meta_json or "",
            }
        )

    if not ids:
        return VectorStoreStatus(ok=False, backend="chroma", message="Sem chunks para indexar")

    col.upsert(ids=ids, documents=docs, metadatas=metadatas)
    return VectorStoreStatus(ok=True, backend="chroma")


def query_chunks(cfg: AppConfig, query: str, *, topk: int | None = None) -> list[RetrievedChunk]:
    q = (query or "").strip()
    if not q:
        return []

    try:
        col = _get_collection(cfg)
    except Exception:
        return []

    k = int(topk or cfg.knowledge_topk)
    try:
        res = col.query(query_texts=[q], n_results=max(1, k))
    except Exception:
        return []

    docs = (res.get("documents") or [[]])[0]
    metadatas = (res.get("metadatas") or [[]])[0]
    distances = (res.get("distances") or [[]])[0]

    out: list[RetrievedChunk] = []
    for doc, meta, dist in zip(docs, metadatas, distances):
        if doc is None:
            continue
        score = 1.0 - float(dist) if dist is not None else 0.0
        if score < float(cfg.knowledge_min_score):
            continue
        chunk = KnowledgeChunk(
            chunk_id=int(meta.get("chunk_id") or 0),
            source=str(meta.get("source") or ""),
            text=str(doc),
            meta_json=str(meta.get("meta_json") or ""),
            added_at=__import__("datetime").datetime.utcnow(),
        )
        out.append(RetrievedChunk(chunk=chunk, score=score))

    out.sort(key=lambda r: r.score, reverse=True)
    return out[: max(1, k)]
