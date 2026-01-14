from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if len(sys.argv) < 2:
        print("Uso: python inference/classify_video.py <path>")
        return 2
    video = sys.argv[1]
    cmd = [sys.executable, str(root / "ia_cli.py"), "video", "--path", video, "--mode", "appearance"]
    return int(subprocess.run(cmd, cwd=str(root)).returncode)


if __name__ == "__main__":
    raise SystemExit(main())
