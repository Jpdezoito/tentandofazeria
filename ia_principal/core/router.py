from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    kind: str  # conversa | buscar | imagem | abrir
    payload: str


_SEARCH_PAT = re.compile(r"^(?:/buscar|buscar\s*:|achar\s*:|procurar\s*:|pesquisar\s*:)(.*)$", re.IGNORECASE)
_OPEN_PAT = re.compile(r"^(?:/abrir)?\s*(\d+)\s*$", re.IGNORECASE)
_OPEN_QUERY_PAT = re.compile(r"^(?:/abrir|abrir|abre)\s+(.+)$", re.IGNORECASE)
_PLAY_PAT = re.compile(r"^(?:tocar|play)\s+(.+)$", re.IGNORECASE)
_YT_PAT = re.compile(r"^(?:/yt|/youtube)\s+(.+)$", re.IGNORECASE)
_YTV_PAT = re.compile(r"^(?:/ytv|/ytvideo)\s+(.+)$", re.IGNORECASE)
_CODE_PAT = re.compile(r"^(?:/codigo|gerar\s+codigo|escrever\s+codigo)\s*:?\s*(.*)$", re.IGNORECASE)


def decide_route(user_text: str) -> RouteDecision:
    t = (user_text or "").strip()
    if not t:
        return RouteDecision("conversa", "")

    m = _OPEN_PAT.match(t)
    if m:
        return RouteDecision("abrir", m.group(1))

    m = _YT_PAT.match(t)
    if m:
        return RouteDecision("yt", (m.group(1) or "").strip())

    m = _YTV_PAT.match(t)
    if m:
        return RouteDecision("ytvideo", (m.group(1) or "").strip())

    m = _OPEN_QUERY_PAT.match(t)
    if m:
        q = (m.group(1) or "").strip()
        return RouteDecision("buscar_abrir", q)

    m = _PLAY_PAT.match(t)
    if m:
        q = (m.group(1) or "").strip()
        return RouteDecision("tocar", q)

    m = _SEARCH_PAT.match(t)
    if m:
        q = (m.group(1) or "").strip()
        return RouteDecision("buscar", q)

    m = _CODE_PAT.match(t)
    if m:
        prompt = (m.group(1) or "").strip()
        return RouteDecision("codigo", prompt)

    # Image is triggered by UI button (file picker) in the app.
    return RouteDecision("conversa", t)
