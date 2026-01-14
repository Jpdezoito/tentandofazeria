from __future__ import annotations

import sys
from pathlib import Path

import tkinter as tk

# Ensure the folder containing the `rna_de_video/` package is on sys.path
_PKG_PARENT = Path(__file__).resolve().parent.parent
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from rna_de_video.app.gui import RnaVideoApp
from rna_de_video.core.config import AppConfig


def main() -> None:
    cfg = AppConfig()
    app = RnaVideoApp(cfg)
    app.title("RNA - Vídeo")
    app.minsize(1200, 760)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        tk._exit()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
