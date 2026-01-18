from __future__ import annotations

import base64
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from core.config import AppConfig


@dataclass(frozen=True)
class OllamaStatus:
    installed: bool
    running: bool
    models: list[str]
    note: str = ""


def is_installed() -> bool:
    return shutil.which("ollama") is not None


def _http_json(url: str, *, method: str = "GET", payload: Optional[dict[str, Any]] = None, timeout_s: float = 10.0) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}


def is_running(cfg: AppConfig) -> bool:
    try:
        _ = list_models_api(cfg)
        return True
    except Exception:
        return False


def list_models_api(cfg: AppConfig) -> list[str]:
    url = cfg.ollama_base_url.rstrip("/") + "/api/tags"
    obj = _http_json(url, method="GET", timeout_s=5.0)
    models = obj.get("models") if isinstance(obj, dict) else None
    out: list[str] = []
    if isinstance(models, list):
        for m in models:
            name = m.get("name") if isinstance(m, dict) else None
            if name:
                out.append(str(name))
    return sorted(set(out))


def list_models_cli() -> list[str]:
    if not is_installed():
        return []
    try:
        cp = subprocess.run(["ollama", "list"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    except Exception:
        return []

    if cp.returncode != 0:
        return []

    lines = [ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return []

    # Format: NAME ID SIZE MODIFIED
    out: list[str] = []
    for ln in lines[1:]:
        parts = ln.split()
        if parts:
            out.append(parts[0])
    return sorted(set(out))


def detect(cfg: AppConfig) -> OllamaStatus:
    if not is_installed():
        return OllamaStatus(installed=False, running=False, models=[], note="Ollama não encontrado no PATH.")

    # Prefer API if running
    try:
        models = list_models_api(cfg)
        return OllamaStatus(installed=True, running=True, models=models)
    except Exception as e:
        # If API is down, still attempt CLI list
        models = list_models_cli()
        note = f"Ollama instalado, mas API não respondeu ({e})."
        return OllamaStatus(installed=True, running=False, models=models, note=note)


def generate(cfg: AppConfig, *, model: str, prompt: str, images: Optional[list[bytes]] = None) -> str:
    """Generate a response using Ollama local API.

    Uses /api/generate with stream=false.
    """

    url = cfg.ollama_base_url.rstrip("/") + "/api/generate"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    if images:
        # Ollama expects base64-encoded images for multimodal models.
        payload["images"] = [base64.b64encode(b).decode("ascii") for b in images]
    try:
        obj = _http_json(url, method="POST", payload=payload, timeout_s=float(cfg.ollama_timeout_s))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama HTTP error: {e.code}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama não respondeu: {e.reason}") from e

    if isinstance(obj, dict) and "response" in obj:
        return str(obj.get("response") or "").strip()
    return ""
