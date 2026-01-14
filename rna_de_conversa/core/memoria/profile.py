from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import treinos_dir, AppConfig


@dataclass(frozen=True)
class UserProfile:
    data: dict[str, Any]


def profile_path(cfg: AppConfig) -> Path:
    return treinos_dir(cfg) / "profile.json"


def load_profile(cfg: AppConfig) -> UserProfile:
    p = profile_path(cfg)
    if not p.exists():
        return UserProfile(data={})
    try:
        return UserProfile(data=json.loads(p.read_text(encoding="utf-8", errors="replace")))
    except Exception:
        return UserProfile(data={})


def save_profile(cfg: AppConfig, data: dict[str, Any]) -> None:
    p = profile_path(cfg)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_preference(cfg: AppConfig, key: str, value: Any) -> None:
    prof = load_profile(cfg)
    data = dict(prof.data)
    data[str(key)] = value
    save_profile(cfg, data)
