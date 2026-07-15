from __future__ import annotations

import os
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEV_ROOT = _PACKAGE_DIR.parents[1]


def _env_path(var: str, default: Path) -> Path:
    val = os.environ.get(var)
    if val:
        return Path(val).resolve()
    return default


PROJECT_ROOT = _DEV_ROOT

DATA_DIR = _env_path("BACMAP_DATA_DIR", _DEV_ROOT / "data")

REF_DIR = DATA_DIR / "reference"

DB_PATH = _env_path("BACMAP_DB_PATH", DATA_DIR / "hermes_bacmap.sqlite")

RESULTS_DIR = _env_path("BACMAP_RESULTS_DIR", _DEV_ROOT / "results")

PIXI_BIN = str(_DEV_ROOT / ".pixi" / "envs" / "default" / "bin")
PIXI_PYTHON = str(_DEV_ROOT / ".pixi" / "envs" / "default" / "bin" / "python")


def pixi_path() -> str:
    return f"{PIXI_BIN}:{os.environ.get('PATH', '')}"


def which(tool: str) -> str | None:
    import shutil
    return shutil.which(tool, path=pixi_path())
