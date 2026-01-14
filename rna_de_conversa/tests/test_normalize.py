from __future__ import annotations

from core.nlp.normalize import tokenize


def test_tokenize_basic() -> None:
    assert tokenize("Olá, você!") == ["ola"]
    assert "acao" in tokenize("Ação rápida")
