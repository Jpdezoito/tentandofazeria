from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    kind: str  # conversa | buscar | imagem | abrir
    payload: str


_SEARCH_PAT = re.compile(r"^(?:/buscar|buscar\s*:|achar\s*:|procurar\s*:|pesquisar\s*:)(.*)$", re.IGNORECASE)
_OPEN_PAT = re.compile(r"^(?:/abrir)\s+(\d+)\s*$", re.IGNORECASE)


def decide_route(user_text: str) -> RouteDecision:
    t = (user_text or "").strip()
    if not t:
        return RouteDecision("conversa", "")

    m = _OPEN_PAT.match(t)
    if m:
        return RouteDecision("abrir", m.group(1))

    m = _SEARCH_PAT.match(t)
    if m:
        q = (m.group(1) or "").strip()
        return RouteDecision("buscar", q)

    # Image is triggered by UI button (file picker) in the app.
    return RouteDecision("conversa", t)
