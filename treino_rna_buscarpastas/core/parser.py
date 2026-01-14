from __future__ import annotations

import re

from core.models import ParsedCommand
from core.normalize import normalize_text


_SAFE_ACTIONS = {
    "abrir": "open",
    "abra": "open",
    "executar": "execute",
    "execute": "execute",
    "iniciar": "execute",
    "inicie": "execute",
    "rodar": "execute",
    "rode": "execute",
}

# A tiny denylist for destructive intents.
_DENY_PATTERNS = [
    r"\bdelet(ar|e|ar)\b",
    r"\bexcluir\b",
    r"\bapagar\b",
    r"\bformat(ar|e|acao|ação)\b",
    r"\bremover\b",
    r"\bdesinstal(ar|e)\b",
]


def parse_command(raw_text: str) -> ParsedCommand:
    """Parse a Portuguese command into a safe intent.

    Supported examples:
    - "abrir chrome"
    - "abrir o word"
    - "executar discord"
    - "abrir pasta downloads"
    - "abrir arquivo planilha.xlsx"

    Returns ParsedCommand with:
    - action: "open" or "execute"
    - query_text: user query without the leading verb (best-effort)
    - query_norm: normalized query for matching
    """

    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Comando vazio.")

    lowered = text.lower().strip()
    for pat in _DENY_PATTERNS:
        if re.search(pat, lowered, flags=re.IGNORECASE):
            raise ValueError("Comandos destrutivos não são permitidos. Use apenas abrir/executar.")

    # Identify leading verb if present.
    tokens = lowered.split()
    action = "open"
    query = text
    if tokens:
        verb = tokens[0]
        if verb in _SAFE_ACTIONS:
            action = _SAFE_ACTIONS[verb]
            query = text[len(tokens[0]) :].strip() or ""

    query = query.strip()
    if not query:
        raise ValueError("Informe o que abrir/executar (ex.: 'abrir chrome').")

    return ParsedCommand(
        action=action,
        raw_text=text,
        query_text=query,
        query_norm=normalize_text(query),
    )
