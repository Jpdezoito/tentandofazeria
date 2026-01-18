from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from core.config import AppConfig, knowledge_index_path
from core.models import KnowledgeChunk, RetrievedChunk
from core.knowledge.store import iter_chunks


@dataclass(frozen=True)
class VectorIndexMeta:
    created_at: str
    total_chunks: int
    max_features: int


@dataclass
class VectorIndex:
    vectorizer: object
    matrix: object
    chunks: list[dict]
    meta: VectorIndexMeta


def _require_sklearn():
    try:
        import joblib  # noqa: F401
        from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: F401
        from sklearn.metrics.pairwise import cosine_similarity  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Dependencias para indice vetorial nao instaladas. "
            "Instale scikit-learn."
        ) from e


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _chunks_to_payload(chunks: Iterable[KnowledgeChunk]) -> list[dict]:
    out: list[dict] = []
    for ch in chunks:
        out.append(
            {
                "chunk_id": int(ch.chunk_id),
                "source": str(ch.source),
                "text": str(ch.text),
                "meta_json": str(ch.meta_json or ""),
                "added_at": ch.added_at.isoformat(),
            }
        )
    return out


def _payload_to_chunks(payload: list[dict]) -> list[KnowledgeChunk]:
    out: list[KnowledgeChunk] = []
    for item in payload:
        out.append(
            KnowledgeChunk(
                chunk_id=int(item.get("chunk_id")),
                source=str(item.get("source") or ""),
                text=str(item.get("text") or ""),
                meta_json=str(item.get("meta_json") or ""),
                added_at=datetime.fromisoformat(str(item.get("added_at"))),
            )
        )
    return out


def build_vector_index(
    cfg: AppConfig,
    chunks: Iterable[KnowledgeChunk],
    *,
    out_path: Path | None = None,
) -> Path | None:
    _require_sklearn()

    from sklearn.feature_extraction.text import TfidfVectorizer
    import joblib

    filtered = [c for c in chunks if (c.text or "").strip()]
    texts = [c.text for c in filtered]
    if not texts:
        return None

    vectorizer = TfidfVectorizer(
        max_features=max(1000, int(cfg.knowledge_index_max_features)),
        ngram_range=(1, 2),
    )
    matrix = vectorizer.fit_transform(texts)

    payload = _chunks_to_payload(filtered)
    meta = VectorIndexMeta(
        created_at=_now_iso(),
        total_chunks=len(payload),
        max_features=int(cfg.knowledge_index_max_features),
    )

    out_path = out_path or knowledge_index_path(cfg)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "vectorizer": vectorizer,
            "matrix": matrix,
            "chunks": payload,
            "meta": meta.__dict__,
        },
        out_path,
    )
    return out_path


def build_vector_index_from_db(cfg: AppConfig, conn, *, out_path: Path | None = None) -> Path | None:
    chunks = list(iter_chunks(conn))
    if not chunks:
        return None
    return build_vector_index(cfg, chunks, out_path=out_path)


def load_vector_index(path: Path) -> VectorIndex | None:
    _require_sklearn()

    import joblib

    if not path.exists():
        return None

    data = joblib.load(path)
    meta_raw = data.get("meta") or {}
    meta = VectorIndexMeta(
        created_at=str(meta_raw.get("created_at") or ""),
        total_chunks=int(meta_raw.get("total_chunks") or 0),
        max_features=int(meta_raw.get("max_features") or 0),
    )
    return VectorIndex(
        vectorizer=data.get("vectorizer"),
        matrix=data.get("matrix"),
        chunks=list(data.get("chunks") or []),
        meta=meta,
    )


def retrieve_with_vector_index(query: str, cfg: AppConfig) -> list[RetrievedChunk]:
    _require_sklearn()

    from sklearn.metrics.pairwise import cosine_similarity

    q = (query or "").strip()
    if not q:
        return []

    idx_path = knowledge_index_path(cfg)
    idx = load_vector_index(idx_path)
    if not idx:
        return []

    vec = idx.vectorizer.transform([q])
    sims = cosine_similarity(vec, idx.matrix).reshape(-1)

    if sims.size == 0:
        return []

    chunks = _payload_to_chunks(idx.chunks)
    scored: list[RetrievedChunk] = []
    for i, score in enumerate(sims.tolist()):
        if score >= float(cfg.knowledge_min_score):
            scored.append(RetrievedChunk(chunk=chunks[i], score=float(score)))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[: max(1, int(cfg.knowledge_topk))]
