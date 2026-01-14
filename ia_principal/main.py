from __future__ import annotations

import sys
from pathlib import Path

import tkinter as tk

_ROOT = Path(__file__).resolve().parent
_PARENT = _ROOT.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

from ia_principal.app.gui import IaPrincipalApp


def main() -> None:
    app = IaPrincipalApp(project_root=_ROOT.parent)
    app.title("IA Principal (Integrada)")
    app.minsize(1080, 720)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        tk._exit()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
