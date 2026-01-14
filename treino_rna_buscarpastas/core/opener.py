from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import AppConfig
from core.models import ItemKind, SearchResult


@dataclass(frozen=True)
class ShortcutResolution:
    target: Optional[Path]
    arguments: str = ""
    working_dir: Optional[Path] = None


def resolve_lnk(path: Path) -> ShortcutResolution:
    """Resolve a .lnk shortcut.

    Uses pywin32 if available; otherwise returns empty target and the caller may fallback to os.startfile.
    """

    try:
        import win32com.client  # type: ignore

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(path))
        target = Path(shortcut.TargetPath) if shortcut.TargetPath else None
        args = str(shortcut.Arguments or "")
        wd = Path(shortcut.WorkingDirectory) if shortcut.WorkingDirectory else None
        return ShortcutResolution(target=target, arguments=args, working_dir=wd)
    except Exception:
        return ShortcutResolution(target=None)


def is_safe_to_execute(path: Path, config: AppConfig) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        return False
    ext = path.suffix.lower()
    if ext in config.executable_exts:
        return True
    if ext in config.shortcut_exts:
        return True
    return False


def open_result(result: SearchResult, action: str, config: AppConfig) -> None:
    """Open/execute a result using the correct Windows mechanism."""

    path = result.path
    if not path.exists():
        raise FileNotFoundError(f"Não encontrado: {path}")

    # Folders and regular files: let Windows decide (Explorer / default app).
    if result.kind in {ItemKind.FOLDER, ItemKind.FILE}:
        os.startfile(str(path))
        return

    if result.kind == ItemKind.SHORTCUT or path.suffix.lower() in config.shortcut_exts:
        # Try to resolve and execute the target; if it fails, fallback to startfile.
        res = resolve_lnk(path)
        if res.target and res.target.exists():
            if res.target.is_dir():
                os.startfile(str(res.target))
                return
            if action == "execute" and is_safe_to_execute(res.target, config):
                args = []
                if res.arguments:
                    # Keep simple: pass arguments as a single string tokenized by Windows.
                    args = [res.arguments]
                subprocess.Popen([str(res.target), *args], cwd=str(res.working_dir) if res.working_dir else None)
                return
            os.startfile(str(res.target))
            return

        os.startfile(str(path))
        return

    # Executables
    if result.kind == ItemKind.EXECUTABLE or path.suffix.lower() in config.executable_exts:
        if action != "execute":
            # If user said "abrir", still start the executable.
            action = "execute"

        if not is_safe_to_execute(path, config):
            raise PermissionError("Extensão não permitida para execução.")

        subprocess.Popen([str(path)])
        return

    # Fallback
    os.startfile(str(path))
