from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def is_allowed_path(path: Path, allowed_roots: Iterable[Path]) -> bool:
    roots = [r for r in allowed_roots if r]
    if not roots:
        return True
    p = path.resolve()
    for r in roots:
        try:
            if p.is_relative_to(r.resolve()):
                return True
        except Exception:
            continue
    return False


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def is_action_allowed(action: str, *, config_path: Path) -> bool:
    cfg = _load_config(config_path)
    perms = cfg.get("permissions", {}) if isinstance(cfg, dict) else {}
    mode = str(perms.get("mode") or "safe").strip().lower()
    if mode == "full":
        return True

    actions = perms.get("actions", {}) if isinstance(perms, dict) else {}
    if not isinstance(actions, dict):
        return True
    val = actions.get(action)
    if val is None:
        return True
    return bool(val)


def is_safe_mode(*, config_path: Path) -> bool:
    cfg = _load_config(config_path)
    perms = cfg.get("permissions", {}) if isinstance(cfg, dict) else {}
    mode = str(perms.get("mode") or "safe").strip().lower()
    return mode != "full"
