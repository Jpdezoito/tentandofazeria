from __future__ import annotations

import re
import unicodedata

# Portuguese stopwords tuned for command-like inputs.
_STOPWORDS = {
    "abrir",
    "abra",
    "executar",
    "execute",
    "iniciar",
    "inicie",
    "rodar",
    "rode",
    "o",
    "a",
    "os",
    "as",
    "um",
    "uma",
    "uns",
    "umas",
    "meu",
    "minha",
    "meus",
    "minhas",
    "do",
    "da",
    "dos",
    "das",
    "de",
    "no",
    "na",
    "nos",
    "nas",
    "para",
    "por",
    "em",
    "pasta",
    "arquivo",
    "app",
    "aplicativo",
    "programa",
}


def strip_accents(text: str) -> str:
    """Remove accents/diacritics from a Unicode string."""

    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_text(text: str) -> str:
    """Normalize user text for consistent matching.

    Steps:
    - lower
    - remove accents
    - replace non-alnum with spaces (keeps dot and underscore/hyphen as separators)
    - collapse whitespace
    - remove stopwords
    """

    lowered = strip_accents(text).lower().strip()
    lowered = re.sub(r"[^a-z0-9._\-\s]", " ", lowered)
    lowered = re.sub(r"[\s_\-]+", " ", lowered)
    tokens = [t for t in lowered.split() if t and t not in _STOPWORDS]
    return " ".join(tokens)


def normalize_name_for_index(name: str) -> str:
    """Normalization used for indexing file/app names.

    Slightly less aggressive than normalize_text: keeps dots to preserve extensions.
    """

    lowered = strip_accents(name).lower().strip()
    lowered = re.sub(r"[^a-z0-9.\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered
