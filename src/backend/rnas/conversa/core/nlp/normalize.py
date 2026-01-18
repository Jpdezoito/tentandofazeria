from __future__ import annotations

import re
import unicodedata


_STOPWORDS = {
    "a",
    "o",
    "os",
    "as",
    "um",
    "uma",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "e",
    "ou",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "pra",
    "para",
    "por",
    "com",
    "que",
    "como",
    "eu",
    "vc",
    "você",
    "voce",
    "me",
    "te",
    "se",
    "isso",
    "essa",
    "esse",
    "isto",
    "aqui",
    "ai",
    "lá",
}


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def normalize_text(text: str) -> str:
    s = strip_accents(text).lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


_TOKEN_RE = re.compile(r"[a-z0-9_]{2,}")


def tokenize(text: str, *, drop_stopwords: bool = True) -> list[str]:
    s = normalize_text(text)
    toks = _TOKEN_RE.findall(s)
    if drop_stopwords:
        toks = [t for t in toks if t not in _STOPWORDS]
    return toks
