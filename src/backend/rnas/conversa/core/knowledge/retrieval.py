from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.models import KnowledgeChunk, RetrievedChunk
from core.nlp.normalize import tokenize


@dataclass(frozen=True)
class KnowledgeRetrievalConfig:
    topk: int = 4
    min_score: float = 0.16


def score_query_to_chunk(query: str, chunk: KnowledgeChunk) -> float:
    qt = tokenize(query)
    ct = tokenize(chunk.text)
    if not qt or not ct:
        return 0.0

    qset = set(qt)
    cset = set(ct)
    inter = len(qset & cset)
    union = len(qset | cset)
    jacc = inter / union if union else 0.0

    qn = " ".join(qt)
    cn = " ".join(ct)
    substr = 0.12 if (qn and cn and (qn in cn or cn in qn)) else 0.0

    length_penalty = 0.0
    if len(ct) > 0 and len(qt) > 0:
        ratio = min(len(qt), len(ct)) / max(len(qt), len(ct))
        length_penalty = 0.08 * ratio

    return float(jacc + substr + length_penalty)


def retrieve_chunks(
    query: str,
    chunks: Iterable[KnowledgeChunk],
    cfg: KnowledgeRetrievalConfig,
) -> list[RetrievedChunk]:
    scored: list[RetrievedChunk] = []
    for ch in chunks:
        s = score_query_to_chunk(query, ch)
        if s >= cfg.min_score:
            scored.append(RetrievedChunk(chunk=ch, score=s))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[: max(1, int(cfg.topk))]
