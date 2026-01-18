from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkConfig:
    max_tokens: int = 420
    overlap: int = 60


def chunk_text(text: str, cfg: ChunkConfig) -> list[str]:
    tokens = (text or "").split()
    if not tokens:
        return []

    max_tokens = max(50, int(cfg.max_tokens))
    overlap = max(0, min(int(cfg.overlap), max_tokens - 1))

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(len(tokens), start + max_tokens)
        chunk = " ".join(tokens[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(tokens):
            break
        start = end - overlap

    return chunks
