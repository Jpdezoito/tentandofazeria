from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class ItemKind(str, Enum):
    FILE = "file"
    FOLDER = "folder"
    EXECUTABLE = "executable"
    SHORTCUT = "shortcut"


@dataclass(frozen=True)
class IndexedItem:
    """An item stored in the local index."""

    path: Path
    display_name: str
    name_norm: str
    kind: ItemKind
    source: str
    mtime: float
    size: int


@dataclass(frozen=True)
class ParsedCommand:
    """Parsed command intent.

    Only supports safe intents: open/execute.
    """

    action: str  # "open" | "execute"
    raw_text: str
    query_text: str
    query_norm: str


@dataclass(frozen=True)
class SearchResult:
    """Search result shown to the user."""

    path: Path
    display_name: str
    kind: ItemKind
    source: str
    score: float
    reason: str
    resolved_target: Optional[Path] = None
