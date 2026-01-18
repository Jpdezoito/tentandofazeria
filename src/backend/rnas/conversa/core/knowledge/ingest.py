from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Document:
    source: str
    text: str


@dataclass(frozen=True)
class IngestStats:
    files: int = 0
    documents: int = 0
    chunks: int = 0
    skipped: int = 0


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._buf: list[str] = []

    def handle_data(self, data: str) -> None:
        if data and data.strip():
            self._buf.append(data.strip())

    def text(self) -> str:
        return "\n".join(self._buf)


def discover_files(target: Path) -> list[Path]:
    p = Path(target)
    if not p.exists():
        return []
    if p.is_file():
        return [p]
    out: list[Path] = []
    for fp in p.rglob("*"):
        if fp.is_file():
            out.append(fp)
    return out


def load_documents(path: Path) -> Iterable[Document]:
    ext = path.suffix.lower()
    if ext in {".txt", ".md", ".json", ".jsonl", ".yaml", ".yml", ".py", ".log", ".csv"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        yield Document(source=str(path), text=text)
        return

    if ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}:
        text_parts: list[str] = []
        try:
            from PIL import Image  # type: ignore
        except Exception:
            return

        try:
            import pytesseract  # type: ignore

            img = Image.open(path)
            ocr = pytesseract.image_to_string(img)
            if ocr and ocr.strip():
                text_parts.append(ocr.strip())
        except Exception:
            pass

        if not text_parts:
            try:
                from transformers import pipeline  # type: ignore

                img = Image.open(path)
                cap = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
                out = cap(img)
                if out and isinstance(out, list) and out[0].get("generated_text"):
                    text_parts.append(str(out[0]["generated_text"]))
            except Exception:
                pass

        if text_parts:
            yield Document(source=str(path), text="\n".join(text_parts))
        return

    if ext in {".html", ".htm"}:
        raw = path.read_text(encoding="utf-8", errors="replace")
        parser = _HTMLTextExtractor()
        parser.feed(raw)
        yield Document(source=str(path), text=parser.text())
        return

    if ext == ".pdf":
        try:
            import PyPDF2  # type: ignore
        except Exception:
            return
        try:
            reader = PyPDF2.PdfReader(str(path))
        except Exception:
            return
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(p for p in parts if p.strip())
        if text.strip():
            yield Document(source=str(path), text=text)
        return

    if ext == ".zip":
        yield from _load_from_zip(path)
        return


def _load_from_zip(path: Path) -> Iterable[Document]:
    try:
        zf = zipfile.ZipFile(path)
    except Exception:
        return

    with zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            inner = Path(name)
            ext = inner.suffix.lower()
            if ext in {".txt", ".md", ".json", ".jsonl", ".yaml", ".yml", ".py", ".log", ".csv", ".html", ".htm"}:
                try:
                    raw = zf.read(name)
                except Exception:
                    continue
                text = raw.decode("utf-8", errors="replace")
                if ext in {".html", ".htm"}:
                    parser = _HTMLTextExtractor()
                    parser.feed(text)
                    text = parser.text()
                if text.strip():
                    src = f"{path}::{name}"
                    yield Document(source=src, text=text)
            elif ext == ".pdf":
                # PDF inside zip is skipped unless user extracts manually.
                continue


def normalize_source_meta(source: str, extra: dict | None = None) -> str:
    meta = {"source": source}
    if extra:
        meta.update(extra)
    return json.dumps(meta, ensure_ascii=False)
