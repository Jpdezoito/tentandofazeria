from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from core.memoria.store import add_example


def _read_text_smart(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    try:
        return data.decode("cp1252")
    except Exception:
        return data.decode("latin-1", errors="replace")


def iter_pairs_from_txt(path: Path) -> Iterable[tuple[str, str]]:
    text = _read_text_smart(path)
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
    for ln in _read_text_smart(path).splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue

        u = (
            obj.get("user")
            or obj.get("usuario")
            or obj.get("pergunta")
            or obj.get("instruction")
            or ""
        ).strip()
        a = (
            obj.get("assistant")
            or obj.get("assistente")
            or obj.get("resposta")
            or obj.get("output")
            or ""
        ).strip()

        if u and a:
            yield (u, a)


def iter_pairs_from_py(path: Path) -> Iterable[tuple[str, str]]:
    text = _read_text_smart(path).strip()
    if not text:
        return
    prompt = f"Arquivo: {path.name}"
    yield (prompt, text)


def import_file(conn, path: Path, seen: set[tuple[str, str]] | None = None) -> int:
    n = 0
    suf = path.suffix.lower()
    if suf == ".txt":
        it = iter_pairs_from_txt(path)
    elif suf in {".jsonl", ".json"}:
        it = iter_pairs_from_jsonl(path)
    elif suf == ".py":
        it = iter_pairs_from_py(path)
    else:
        return 0

    for u, a in it:
        key = (u, a)
        if seen is not None:
            if key in seen:
                continue
            seen.add(key)
        add_example(conn, u, a)
        n += 1
    return n
