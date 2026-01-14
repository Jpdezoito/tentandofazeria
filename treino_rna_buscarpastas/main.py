from __future__ import annotations

import tkinter as tk

from app.gui import RnaApp
from core.config import aliases_path, config_from_env, index_db_path, stats_path
from core.storage import PreferenceStore


def main() -> None:
    config = config_from_env()
    store = PreferenceStore(aliases_path=aliases_path(config), stats_path=stats_path(config))
    store.ensure_files()

    app = RnaApp(config=config, store=store, db_path=index_db_path(config))
    app.title("RNA - Assistente")
    app.minsize(980, 640)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        # Allow graceful exit if run from a console.
        tk._exit()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
