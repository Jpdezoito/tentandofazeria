from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Literal


Role = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class Turn:
    role: Role
    text: str
    at: datetime


class SessionMemory:
    def __init__(self, max_turns: int = 12):
        self.max_turns = max(2, int(max_turns))
        self._turns: Deque[Turn] = deque(maxlen=self.max_turns)

    def clear(self) -> None:
        self._turns.clear()

    def add(self, role: Role, text: str) -> None:
        self._turns.append(Turn(role=role, text=text, at=datetime.now(timezone.utc)))

    def as_prompt(self, *, system_preamble: str | None = None) -> str:
        parts: list[str] = []
        if system_preamble:
            parts.append(f"[system]\n{system_preamble}\n")
        for t in self._turns:
            parts.append(f"[{t.role}]\n{t.text}\n")
        return "\n".join(parts).strip() + "\n"
