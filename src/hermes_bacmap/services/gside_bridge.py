"""gside CLI bridge — bacmap calls gside for species identification.

When gside is installed (pip install -e ~/repos/github/gside), bacmap
delegates species identification to the independent CLI tool; when absent,
smk rules fall back to bacmap's internal analysis modules.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ..config import which

_TIMEOUT_S = 900


def gside_available() -> bool:
    return which("gside") is not None


def gside_species(
    contigs: str | Path, mode: str = "marker", db_dir: str | Path | None = None
) -> dict[str, Any] | None:
    bin_path = which("gside")
    if not bin_path:
        return None

    cmd = [bin_path, "species", str(contigs), "--mode", mode, "--json"]
    if db_dir:
        cmd += ["--db-dir", str(db_dir)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError):
        return None

    if result.returncode != 0:
        return None

    try:
        data: dict[str, Any] = json.loads(result.stdout)
        return data
    except json.JSONDecodeError:
        return None
