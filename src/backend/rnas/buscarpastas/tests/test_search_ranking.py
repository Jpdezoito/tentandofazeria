from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.config import AppConfig
from core.index_db import DbItemRow, init_db, upsert_items
from core.search import SearchParams, search
from core.storage import PreferenceStore


def test_preference_beats_everything(tmp_path: Path) -> None:
    config = AppConfig(enable_drive_scan=False)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    upsert_items(
        conn,
        rows=[
            DbItemRow(
                path=str(tmp_path / "Chrome.exe"),
                display_name="Chrome.exe",
                name_norm="chrome.exe",
                kind="executable",
                source="programfiles",
                mtime=1.0,
                size=123,
                ext=".exe",
            ),
            DbItemRow(
                path=str(tmp_path / "Chrome.lnk"),
                display_name="Chrome.lnk",
                name_norm="chrome.lnk",
                kind="shortcut",
                source="startmenu_user",
                mtime=1.0,
                size=123,
                ext=".lnk",
            ),
        ],
        scan_id=1,
    )
    conn.commit()

    aliases = tmp_path / "aliases.json"
    stats = tmp_path / "stats.json"
    aliases.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    stats.write_text(
        json.dumps({"preferences": {"chrome": str(tmp_path / "Chrome.lnk")}, "usage": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    store = PreferenceStore(aliases_path=aliases, stats_path=stats)

    results = search(
        conn,
        store,
        config,
        SearchParams(query_text="chrome", query_norm="chrome", action="open"),
        cancel_event=None,
        log=None,
    )

    assert results
    assert str(results[0].path).endswith("Chrome.lnk")


def test_source_weight_can_break_ties(tmp_path: Path) -> None:
    config = AppConfig(enable_drive_scan=False, min_fuzzy_score=0)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    upsert_items(
        conn,
        rows=[
            DbItemRow(
                path=str(tmp_path / "ABC.txt"),
                display_name="ABC",
                name_norm="abc",
                kind="file",
                source="desktop",
                mtime=1.0,
                size=1,
                ext=".txt",
            ),
            DbItemRow(
                path=str(tmp_path / "ABC2.txt"),
                display_name="ABC",
                name_norm="abc",
                kind="file",
                source="drive_c",
                mtime=1.0,
                size=1,
                ext=".txt",
            ),
        ],
        scan_id=1,
    )
    conn.commit()

    aliases = tmp_path / "aliases.json"
    stats = tmp_path / "stats.json"
    aliases.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    stats.write_text(json.dumps({"preferences": {}, "usage": {}}, ensure_ascii=False), encoding="utf-8")
    store = PreferenceStore(aliases_path=aliases, stats_path=stats)

    results = search(
        conn,
        store,
        config,
        SearchParams(query_text="abc", query_norm="abc", action="open"),
        cancel_event=None,
        log=None,
    )
    assert results
    assert results[0].source == "desktop"
