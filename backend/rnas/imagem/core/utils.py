from __future__ import annotations

import hashlib
from pathlib import Path


def sha1_text(text: str) -> str:
    h = hashlib.sha1()
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def embedding_key_for_file(path: Path) -> str:
    """Generate a stable-ish embedding cache key for a file.

    Uses absolute path + mtime + size so updates invalidate cache.
    """

    p = path.resolve()
    try:
        st = p.stat()
        sig = f"{p}|{st.st_mtime_ns}|{st.st_size}"
    except OSError:
        sig = f"{p}"
    return sha1_text(sig)
