from __future__ import annotations

import hashlib
import importlib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from rna_de_video.core.config import AppConfig, imported_videos_dir


_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}


def is_video_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in _VIDEO_EXTS


def resolve_video_path(ref: str) -> Path:
    s = (ref or "").strip().strip('"\'')
    if not s:
        raise ValueError("Caminho do vídeo vazio.")

    p = Path(s)
    try:
        p = p.expanduser()
    except Exception:
        pass
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()

    if not p.exists():
        raise ValueError("Arquivo de vídeo não encontrado.")
    if not p.is_file():
        raise ValueError("O caminho não aponta para um arquivo.")
    if p.suffix.lower() not in _VIDEO_EXTS:
        raise ValueError(f"Extensão não suportada ({p.suffix}). Use: {', '.join(sorted(_VIDEO_EXTS))}")

    return p


def _guess_ext_from_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        ext = Path(parsed.path).suffix.lower()
        if ext in _VIDEO_EXTS:
            return ext
    except Exception:
        pass
    return ".mp4"


def _is_direct_video_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        ext = Path(parsed.path).suffix.lower()
        return ext in _VIDEO_EXTS
    except Exception:
        return False


def _looks_like_youtube(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.netloc or "").lower()
        return "youtube.com" in host or "youtu.be" in host
    except Exception:
        return False


def download_video_ytdlp_to_file(
    config: AppConfig,
    url: str,
    *,
    max_bytes: int | None = None,
) -> Path:
    """Download a video URL using yt-dlp (optional dependency).

    Intended for YouTube/short links and other pages that are not direct .mp4 URLs.
    """

    u = (url or "").strip()
    if not u:
        raise ValueError("URL vazia.")

    try:
        yt_dlp = importlib.import_module("yt_dlp")
        YoutubeDL = getattr(yt_dlp, "YoutubeDL")
    except Exception as e:
        raise RuntimeError(
            "Para baixar vídeos do YouTube (ou links não-diretos), instale: pip install yt-dlp"
        ) from e

    limit = int(max_bytes if max_bytes is not None else config.video_url_max_bytes)
    digest = hashlib.sha1(u.encode("utf-8")).hexdigest()[:16]
    outtmpl = str(imported_videos_dir(config) / f"yt_{digest}.%(ext)s")

    # Prefer mp4 when available; otherwise fall back to best available.
    # Note: many YouTube videos expose separate video/audio streams; selecting a
    # combined format can require ffmpeg to merge. To keep the pipeline working
    # without ffmpeg, we prefer VIDEO-ONLY formats (bestvideo) first.
    opts = {
        "outtmpl": outtmpl,
        "format": "bestvideo[ext=mp4]/bestvideo/best[ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": limit,
    }

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(u, download=True)

    if not isinstance(info, dict):
        raise RuntimeError("yt-dlp não retornou metadata válida.")

    # yt-dlp may return a playlist dict even with noplaylist; handle fallback.
    if "entries" in info and isinstance(info.get("entries"), list):
        entries = [e for e in info.get("entries") if isinstance(e, dict)]
        if not entries:
            raise RuntimeError("yt-dlp não achou entradas para baixar.")
        info = entries[0]

    fp = info.get("filepath") or info.get("_filename")
    if fp:
        p = Path(str(fp))
        if p.exists() and p.is_file():
            return p

    # Fallback: find any yt_{digest}.* in imported_videos_dir
    folder = imported_videos_dir(config)
    cand = sorted(folder.glob(f"yt_{digest}.*"))
    for p in cand:
        if p.is_file() and p.suffix.lower() in _VIDEO_EXTS:
            return p

    raise RuntimeError("Download concluído, mas não achei o arquivo final.")


def download_video_url_to_file(
    config: AppConfig,
    url: str,
    *,
    timeout_s: float | None = None,
    max_bytes: int | None = None,
) -> Path:
    u = (url or "").strip()
    if not u:
        raise ValueError("URL vazia.")

    parsed = urllib.parse.urlparse(u)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Somente URLs http(s) são suportadas para vídeo.")

    timeout = float(timeout_s if timeout_s is not None else config.video_url_timeout_s)
    limit = int(max_bytes if max_bytes is not None else config.video_url_max_bytes)

    req = urllib.request.Request(
        u,
        headers={
            "User-Agent": "RNA_Video/1.0",
            "Accept": "video/*,*/*;q=0.8",
        },
        method="GET",
    )

    chunks: list[bytes] = []
    total = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            while True:
                chunk = resp.read(128 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    raise ValueError(f"Download excedeu limite de {limit} bytes.")
    except urllib.error.HTTPError as e:
        raise ValueError(f"HTTP {e.code} ao baixar vídeo.") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Falha de rede ao baixar vídeo: {e.reason}") from e

    raw = b"".join(chunks)
    if not raw:
        raise ValueError("Vídeo baixado veio vazio.")

    ext = _guess_ext_from_url(u)
    digest = hashlib.sha1(u.encode("utf-8")).hexdigest()[:16]
    out = imported_videos_dir(config) / f"url_{digest}{ext}"
    if out.exists():
        return out
    out.write_bytes(raw)
    return out


def resolve_video_reference_to_file(config: AppConfig, ref: str) -> Path:
    """Resolve a video reference into a local file.

    Accepts:
    - Local file path
    - http(s) URL (downloaded into treinos/imported_videos)
    """

    s = (ref or "").strip().strip('"\'')
    if not s:
        raise ValueError("Endereço/URL vazio.")

    parsed = urllib.parse.urlparse(s)
    if (parsed.scheme or "").lower() in {"http", "https"}:
        # Direct file URLs (mp4/mkv/etc)
        if _is_direct_video_url(s):
            return download_video_url_to_file(config, s)

        # YouTube and other non-direct sources (optional)
        if _looks_like_youtube(s):
            return download_video_ytdlp_to_file(config, s)

        # Try direct download anyway (some hosts hide extension)
        return download_video_url_to_file(config, s)

    return resolve_video_path(s)


def list_videos_in_folder(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    out: list[Path] = []
    for p in folder.rglob("*"):
        if is_video_file(p):
            out.append(p)
    return sorted(out)
