from __future__ import annotations

import os
import shutil
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIXI_BIN = str(_PROJECT_ROOT / ".pixi" / "envs" / "default" / "bin")
VENV_BIN = str(_PROJECT_ROOT / ".venv" / "bin")


def pixi_path() -> str:
    return f"{PIXI_BIN}:{os.environ.get('PATH', '')}"


def which(tool: str) -> str | None:
    return shutil.which(tool, path=pixi_path())
