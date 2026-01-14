from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Example:
    example_id: int
    user_text: str
    assistant_text: str
    added_at: datetime


@dataclass(frozen=True)
class Retrieved:
    example: Example
    score: float
