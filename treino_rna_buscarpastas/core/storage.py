from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class PreferenceStore:
    """Stores aliases and usage statistics.

    Files:
    - aliases.json: manual aliases like {"chrome": "C:\\...\\chrome.exe"}
    - stats.json: learned preferences and usage stats.
    """

    aliases_path: Path
    stats_path: Path

    def ensure_files(self) -> None:
        self.aliases_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.aliases_path.exists():
            self.aliases_path.write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding="utf-8")
        if not self.stats_path.exists():
            initial = {"preferences": {}, "usage": {}}
            self.stats_path.write_text(json.dumps(initial, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_aliases(self) -> Dict[str, str]:
        self.ensure_files()
        try:
            data = json.loads(self.aliases_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def load_stats(self) -> Dict[str, Any]:
        self.ensure_files()
        try:
            data = json.loads(self.stats_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("preferences", {})
                data.setdefault("usage", {})
                return data
        except Exception:
            pass
        return {"preferences": {}, "usage": {}}

    def get_preference_for_query(self, query_norm: str) -> Optional[str]:
        stats = self.load_stats()
        pref = stats.get("preferences", {}).get(query_norm)
        return str(pref) if pref else None

    def set_preference_for_query(self, query_norm: str, path: str) -> None:
        stats = self.load_stats()
        prefs = stats.setdefault("preferences", {})
        prefs[query_norm] = path
        self.stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_open(self, path: str) -> None:
        stats = self.load_stats()
        usage: Dict[str, Any] = stats.setdefault("usage", {})
        row = usage.setdefault(path, {"count": 0, "last_opened": None})
        row["count"] = int(row.get("count") or 0) + 1
        row["last_opened"] = _utc_now_iso()
        self.stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_usage(self, path: str) -> tuple[int, Optional[str]]:
        stats = self.load_stats()
        row = stats.get("usage", {}).get(path)
        if not isinstance(row, dict):
            return 0, None
        return int(row.get("count") or 0), (row.get("last_opened") or None)
