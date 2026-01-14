from __future__ import annotations

import os
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SearchRoot:
    name: str
    path: Path


def _env_path(var: str) -> Path | None:
    value = os.environ.get(var)
    if not value:
        return None
    p = Path(value)
    return p if p.exists() else None


def get_standard_roots() -> list[SearchRoot]:
    """Return the standardized search roots in the requested order."""

    roots: list[SearchRoot] = []

    user_profile = _env_path("USERPROFILE")
    public = _env_path("PUBLIC")

    # 1) Desktop
    if user_profile:
        desktop = user_profile / "Desktop"
        if desktop.exists():
            roots.append(SearchRoot("desktop", desktop))

    # 2) Known user folders
    if user_profile:
        for name, folder in [
            ("documents", "Documents"),
            ("downloads", "Downloads"),
            ("pictures", "Pictures"),
            ("videos", "Videos"),
        ]:
            p = user_profile / folder
            if p.exists():
                roots.append(SearchRoot(name, p))

    # 3) Start Menu shortcuts
    if user_profile:
        p = user_profile / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if p.exists():
            roots.append(SearchRoot("startmenu_user", p))

    program_data = _env_path("ProgramData")
    if program_data:
        p = program_data / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if p.exists():
            roots.append(SearchRoot("startmenu_programdata", p))

    # 4) Program Files
    for env_name, root_name in [("ProgramFiles", "programfiles"), ("ProgramFiles(x86)", "programfiles_x86")]:
        p = _env_path(env_name)
        if p:
            roots.append(SearchRoot(root_name, p))

    # 5) AppData
    if user_profile:
        roaming = user_profile / "AppData" / "Roaming"
        local = user_profile / "AppData" / "Local"
        if roaming.exists():
            roots.append(SearchRoot("appdata_roaming", roaming))
        if local.exists():
            roots.append(SearchRoot("appdata_local", local))

    # Public Desktop sometimes contains common shortcuts.
    if public:
        pd = public / "Desktop"
        if pd.exists():
            roots.append(SearchRoot("public_desktop", pd))

    return roots


def iter_local_drives() -> Iterable[str]:
    """Yield drive roots like 'C:\\' that exist."""

    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            yield drive
