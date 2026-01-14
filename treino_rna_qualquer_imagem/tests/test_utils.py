from pathlib import Path

from core.utils import embedding_key_for_file


def test_embedding_key_changes_on_mtime(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("x", encoding="utf-8")
    k1 = embedding_key_for_file(p)
    p.write_text("y", encoding="utf-8")
    k2 = embedding_key_for_file(p)
    assert k1 != k2
