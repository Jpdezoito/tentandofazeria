from __future__ import annotations

import sys
from pathlib import Path

import tkinter as tk

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.gui import RnaConversaApp
from core.config import AppConfig


def main() -> None:
    cfg = AppConfig()
    app = RnaConversaApp(cfg)
    app.title("RNA - Conversa")
    app.minsize(1120, 720)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        tk._exit()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
