from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class DatasetEntry:
    name: str
    path: str
    sha256: str
    size_bytes: int
    records: int
    created_at: str
    meta: dict


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_records(path: Path) -> int:
    if path.suffix.lower() in {".jsonl", ".txt"}:
        return len([ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()])
    if path.suffix.lower() == ".json":
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(obj, list):
                return len(obj)
        except Exception:
            return 0
    return 0


def _load_index(index_path: Path) -> dict:
    if not index_path.exists():
        return {"datasets": []}
    try:
        return json.loads(index_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"datasets": []}


def register_dataset(index_path: Path, entry: DatasetEntry) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_index(index_path)
    ds = list(data.get("datasets") or [])
    ds.append(
        {
            "name": entry.name,
            "path": entry.path,
            "sha256": entry.sha256,
            "size_bytes": entry.size_bytes,
            "records": entry.records,
            "created_at": entry.created_at,
            "meta": entry.meta or {},
        }
    )
    data["datasets"] = ds
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_entry(name: str, path: Path, created_at: str, meta: dict | None = None) -> DatasetEntry:
    p = path.expanduser().resolve()
    return DatasetEntry(
        name=name,
        path=str(p),
        sha256=_sha256_file(p),
        size_bytes=p.stat().st_size,
        records=_count_records(p),
        created_at=created_at,
        meta=meta or {},
    )
