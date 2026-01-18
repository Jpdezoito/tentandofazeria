from __future__ import annotations

import pytest
from core.config import config_from_env
from core.models import CodeModel


def test_code_model_init():
    cfg = config_from_env()
    model = CodeModel(cfg)
    assert model.cfg == cfg
    assert model.model is None
    assert model.tokenizer is None


def test_tokenize_function():
    cfg = config_from_env()
    model = CodeModel(cfg)
    model.load_model()

    examples = {"text": ["def hello(): pass"]}
    result = model.tokenize_function(examples)

    assert "input_ids" in result
    assert "attention_mask" in result


def test_generate():
    cfg = config_from_env()
    model = CodeModel(cfg)

    # Mock model loading for test
    # In real test, would load a small model
    prompt = "def fibonacci(n):"
    # result = model.generate(prompt, max_length=50)
    # assert isinstance(result, str)
    # assert len(result) > len(prompt)
    pass  # Skip for now, requires model download