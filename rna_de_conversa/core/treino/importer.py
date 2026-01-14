from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from core.memoria.store import add_example


def iter_pairs_from_txt(path: Path) -> Iterable[tuple[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln.rstrip() for ln in text.splitlines()]

    buf: list[str] = []
    for ln in lines + [""]:
        if not ln.strip():
            if len(buf) >= 2:
                u = _strip_prefix(buf[0])
                a = _strip_prefix(buf[1])
                if u and a:
                    yield (u, a)
            buf = []
            continue
        buf.append(ln)
        if len(buf) == 2:
            # allow pairs without blank line
            u = _strip_prefix(buf[0])
            a = _strip_prefix(buf[1])
            if u and a:
                yield (u, a)
            buf = []


def _strip_prefix(line: str) -> str:
    s = line.strip()
    for prefix in ("usuario:", "user:", "u:", "pergunta:", "assistente:", "assistant:", "a:", "resposta:"):
        if s.lower().startswith(prefix):
            return s[len(prefix) :].strip()
    return s


def iter_pairs_from_jsonl(path: Path) -> Iterable[tuple[str, str]]:
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        u = (obj.get("user") or obj.get("usuario") or obj.get("pergunta") or "").strip()
        a = (obj.get("assistant") or obj.get("assistente") or obj.get("resposta") or "").strip()
        if u and a:
            yield (u, a)


def import_file(conn, path: Path) -> int:
    n = 0
    suf = path.suffix.lower()
    if suf == ".txt":
        it = iter_pairs_from_txt(path)
    elif suf in {".jsonl", ".json"}:
        it = iter_pairs_from_jsonl(path)
    else:
        return 0

    for u, a in it:
        add_example(conn, u, a)
        n += 1
    return n


def import_folder(conn, folder: Path) -> tuple[int, list[str]]:
    errors: list[str] = []
    imported = 0
    if not folder.exists():
        return (0, errors)

    for p in sorted(folder.glob("**/*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".txt", ".jsonl", ".json"}:
            continue
        try:
            imported += import_file(conn, p)
        except Exception as e:
            errors.append(f"{p.name}: {e}")

    return (imported, errors)
