from __future__ import annotations

from datetime import datetime

from core.models import Example
from core.retrieval.retriever import RetrievalConfig, retrieve


def test_retrieve_basic() -> None:
    t = datetime.fromisoformat("2020-01-01T00:00:00")
    exs = [
        Example(example_id=1, user_text="como abrir o chrome?", assistant_text="use o menu iniciar", added_at=t),
        Example(example_id=2, user_text="qual é seu nome", assistant_text="sou a rna", added_at=t),
    ]

    hits = retrieve("abrir chrome", exs, RetrievalConfig(topk=2, min_score=0.01))
    assert hits
    assert hits[0].example.example_id == 1
