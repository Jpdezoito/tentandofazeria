from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.models import Example, Retrieved
from core.nlp.normalize import tokenize


@dataclass(frozen=True)
class RetrievalConfig:
    topk: int = 3
    min_score: float = 0.18


def score_query_to_example(query: str, ex: Example) -> float:
    qt = tokenize(query)
    et = tokenize(ex.user_text)
    if not qt or not et:
        return 0.0

    qset = set(qt)
    eset = set(et)

    inter = len(qset & eset)
    union = len(qset | eset)
    jacc = inter / union if union else 0.0

    # Boost if query is a substring of stored question (or vice-versa)
    qn = " ".join(qt)
    en = " ".join(et)
    substr = 0.15 if (qn and en and (qn in en or en in qn)) else 0.0

    # Small length normalization
    length_penalty = 0.0
    if len(et) > 0 and len(qt) > 0:
        ratio = min(len(qt), len(et)) / max(len(qt), len(et))
        length_penalty = 0.10 * ratio

    return float(jacc + substr + length_penalty)


def retrieve(query: str, examples: Iterable[Example], cfg: RetrievalConfig) -> list[Retrieved]:
    scored: list[Retrieved] = []
    for ex in examples:
        s = score_query_to_example(query, ex)
        if s >= cfg.min_score:
            scored.append(Retrieved(example=ex, score=s))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[: max(1, int(cfg.topk))]
