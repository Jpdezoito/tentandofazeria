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


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: int
    source: str
    text: str
    added_at: datetime
    meta_json: str = ""


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: KnowledgeChunk
    score: float
