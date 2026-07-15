from __future__ import annotations

import os
import shutil

from hermes_bacmap.config import PROJECT_ROOT as _PROJECT_ROOT
from hermes_bacmap.config import PIXI_BIN, PIXI_PYTHON


def pixi_path() -> str:
    return f"{PIXI_BIN}:{os.environ.get('PATH', '')}"


def which(tool: str) -> str | None:
    return shutil.which(tool, path=pixi_path())
