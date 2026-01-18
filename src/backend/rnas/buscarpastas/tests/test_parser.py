import pytest

from core.parser import parse_command


def test_parse_open_default() -> None:
    cmd = parse_command("abrir o word")
    assert cmd.action == "open"
    assert cmd.query_norm == "word"


def test_parse_execute() -> None:
    cmd = parse_command("executar discord")
    assert cmd.action == "execute"
    assert cmd.query_norm == "discord"


def test_parse_denies_destructive() -> None:
    with pytest.raises(ValueError):
        parse_command("deletar arquivos")
