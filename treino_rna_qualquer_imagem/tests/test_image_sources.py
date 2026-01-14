from __future__ import annotations

import base64
from pathlib import Path

import pytest

from core.config import AppConfig
from core.image_sources import parse_data_url, resolve_image_reference_to_file


def test_parse_data_url_png_roundtrip() -> None:
    # Minimal 1x1 PNG
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/ax5m8cAAAAASUVORK5CYII="
    )
    url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    mime, raw = parse_data_url(url)
    assert mime == "image/png"
    assert raw == png_bytes


def test_parse_data_url_invalid() -> None:
    with pytest.raises(ValueError):
        parse_data_url("data:image/png;base64,not_base64!!!!")


def test_resolve_local_path(tmp_path: Path) -> None:
    p = tmp_path / "x.png"
    p.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/ax5m8cAAAAASUVORK5CYII="
        )
    )
    cfg = AppConfig()
    out = resolve_image_reference_to_file(cfg, str(p))
    assert out.exists()
    assert out.resolve() == p.resolve()


def test_resolve_file_url(tmp_path: Path) -> None:
    p = tmp_path / "y.png"
    p.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/ax5m8cAAAAASUVORK5CYII="
        )
    )
    cfg = AppConfig()
    # Use POSIX-like file URL; resolver uses url2pathname which handles Windows too.
    url = p.resolve().as_uri()
    out = resolve_image_reference_to_file(cfg, url)
    assert out.exists()
    assert out.resolve() == p.resolve()
