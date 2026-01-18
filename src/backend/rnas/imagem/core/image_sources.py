from __future__ import annotations

import base64
import binascii
import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from core.config import AppConfig


_DATA_URL_RE = re.compile(
    r"^data:(?P<mime>[-\w.]+/[-\w.+]+)?(?P<params>(?:;[-\w.+]+=*[-\w.+:]*)*);base64,(?P<data>.*)$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class UrlImageBytes:
    """Raw bytes fetched from a URL-like source."""

    source: str  # "data" | "http" | "https"
    mime: Optional[str]
    data: bytes


def parse_data_url(data_url: str) -> Tuple[Optional[str], bytes]:
    """Parse a data URL of form data:<mime>;base64,<payload>."""

    m = _DATA_URL_RE.match(data_url.strip())
    if not m:
        raise ValueError("URL 'data:' inválida (esperado data:<mime>;base64,<...>).")

    mime = m.group("mime")
    payload = m.group("data")

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"Base64 inválido na data URL: {e}") from e

    return (mime, raw)


def fetch_url_bytes(url: str, *, timeout_s: float = 15.0, max_bytes: int = 12 * 1024 * 1024) -> UrlImageBytes:
    """Fetch bytes from a supported URL.

    Supports:
    - data:image/...;base64,...
    - http(s) URLs

    Limits total downloaded bytes to max_bytes.
    """

    u = url.strip()
    if not u:
        raise ValueError("URL vazia.")

    if u.lower().startswith("data:"):
        mime, raw = parse_data_url(u)
        if len(raw) > max_bytes:
            raise ValueError(f"Imagem muito grande na data URL ({len(raw)} bytes). Limite: {max_bytes}.")
        return UrlImageBytes(source="data", mime=mime, data=raw)

    parsed = urllib.parse.urlparse(u)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Somente URLs http(s) ou data:...;base64 são suportadas.")

    req = urllib.request.Request(
        u,
        headers={
            "User-Agent": "RNA_Qualquer_Imagem/1.0",
            "Accept": "image/*,*/*;q=0.8",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            content_type = resp.headers.get("Content-Type")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Download excedeu limite de {max_bytes} bytes.")
            raw = b"".join(chunks)
    except urllib.error.HTTPError as e:
        raise ValueError(f"HTTP {e.code} ao baixar imagem.") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Falha de rede ao baixar imagem: {e.reason}") from e

    return UrlImageBytes(source=parsed.scheme.lower(), mime=content_type, data=raw)


def imported_images_dir(config: AppConfig) -> Path:
    d = _treinos_dir(config) / "imported_images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_url_image_as_png(
    config: AppConfig,
    url: str,
    *,
    timeout_s: float = 15.0,
    max_bytes: int = 12 * 1024 * 1024,
    filename_prefix: str = "url",
) -> Path:
    """Download/decode URL image, validate with Pillow, and save under treinos/imported_images as PNG."""

    blob = fetch_url_bytes(url, timeout_s=timeout_s, max_bytes=max_bytes)

    try:
        img = Image.open(BytesIO(blob.data))
        img = img.convert("RGB")
    except Exception as e:
        raise ValueError(f"Conteúdo baixado não parece ser uma imagem válida: {e}") from e

    digest = hashlib.sha1(blob.data).hexdigest()
    out = imported_images_dir(config) / f"{filename_prefix}_{blob.source}_{digest}.png"

    # Avoid overwriting if exists (still deterministic enough)
    if out.exists():
        return out

    img.save(out, format="PNG", optimize=True)
    return out


def resolve_image_reference_to_file(
    config: AppConfig,
    ref: str,
    *,
    timeout_s: float = 15.0,
    max_bytes: int = 12 * 1024 * 1024,
    filename_prefix: str = "ref",
) -> Path:
    """Resolve an image reference to a local file path.

    Accepts:
    - Local file path: C:\\...\\img.jpg, \\server\\share\\img.png, relative paths
    - file:// URLs
    - http(s) URLs (downloaded into treinos/imported_images/ as PNG)
    - data:image/...;base64,... (decoded into treinos/imported_images/ as PNG)
    """

    s = (ref or "").strip().strip("\"'")
    if not s:
        raise ValueError("Endereço/URL vazio.")

    if s.lower().startswith("data:"):
        return save_url_image_as_png(
            config,
            s,
            timeout_s=timeout_s,
            max_bytes=max_bytes,
            filename_prefix=filename_prefix,
        )

    parsed = urllib.parse.urlparse(s)
    scheme = (parsed.scheme or "").lower()
    if scheme in {"http", "https"}:
        return save_url_image_as_png(
            config,
            s,
            timeout_s=timeout_s,
            max_bytes=max_bytes,
            filename_prefix=filename_prefix,
        )

    if scheme == "file":
        # file:///C:/path/to/img.png
        local_path = urllib.request.url2pathname(parsed.path)
        p = Path(local_path)
        if not p.exists():
            raise ValueError("Arquivo não encontrado no caminho file:// fornecido.")
        if not p.is_file():
            raise ValueError("O caminho file:// não aponta para um arquivo.")
        return p

    # Otherwise treat as local path
    p = Path(s)
    try:
        p = p.expanduser()
    except Exception:
        pass
    if not p.is_absolute():
        # Prefer resolving relative to current working directory.
        p = (Path.cwd() / p).resolve()
    if not p.exists():
        raise ValueError("Arquivo não encontrado nesse endereço de imagem.")
    if not p.is_file():
        raise ValueError("Esse endereço não é um arquivo.")
    return p


def _treinos_dir(config: AppConfig) -> Path:
    # Local import to avoid circulars in some environments
    from core.config import treinos_dir

    return treinos_dir(config)
