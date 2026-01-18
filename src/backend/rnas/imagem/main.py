from __future__ import annotations

import tkinter as tk

from app.gui import RnaImageApp
from core.config import config_from_env


def main() -> None:
    config = config_from_env()
    app = RnaImageApp(config=config)
    app.title("RNA - Qualquer Imagem (Open-World)")
    app.minsize(1120, 720)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        tk._exit()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
