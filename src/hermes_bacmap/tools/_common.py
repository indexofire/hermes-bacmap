"""Shared infrastructure for tool handlers.

Holds config aliases, subprocess helpers, the Biopython availability check,
and the tool_handler catch-all decorator. Submodules import the names they
need so tests can monkeypatch them per-module.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from hermes_bacmap.config import (
    DB_PATH as _DEFAULT_DB_PATH,
)
from hermes_bacmap.config import PIXI_BIN, PIXI_PYTHON
from hermes_bacmap.config import (
    PROJECT_ROOT as _PROJECT_ROOT,
)
from hermes_bacmap.config import (
    RESULTS_DIR as _RESULTS_DIR,
)

__all__ = [
    "_BIOPYTHON_AVAILABLE",
    "_DEFAULT_DB_PATH",
    "_PIXI_ENV",
    "_PROJECT_ROOT",
    "_RESULTS_DIR",
    "_detect_format",
    "_ensure_biopython",
    "_resolve_path",
    "_run_cmd",
    "_run_project_script",
    "_which_or_error",
    "logger",
    "tool_handler",
]

logger = logging.getLogger(__name__)

_BIOPYTHON_AVAILABLE: bool | None = None


_PIXI_ENV: dict[str, str] = dict(os.environ)
_PIXI_ENV["PATH"] = ":".join([PIXI_BIN, _PIXI_ENV.get("PATH", "")])


def _run_project_script(script_name: str, args: list[str], timeout: int = 3600) -> str:
    """Run a script from scripts/ with pixi PATH injected. Returns stdout or error JSON."""
    env = dict(_PIXI_ENV)
    cmd = [PIXI_PYTHON, str(_PROJECT_ROOT / "scripts" / script_name)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    if result.returncode != 0:
        return json.dumps({"error": f"{script_name} failed", "stderr": result.stderr[-500:]})
    return result.stdout


def _ensure_biopython() -> bool:
    """Return True if Biopython can be imported; try lazy install once."""
    global _BIOPYTHON_AVAILABLE
    if _BIOPYTHON_AVAILABLE is not None:
        return _BIOPYTHON_AVAILABLE
    try:
        import Bio  # noqa: F401

        _BIOPYTHON_AVAILABLE = True
        return True
    except ImportError:
        pass
    try:
        subprocess.run(
            [PIXI_PYTHON, "-m", "pip", "install", "biopython"],
            check=True,
            capture_output=True,
            timeout=120,
        )
        import Bio  # noqa: F401

        _BIOPYTHON_AVAILABLE = True
        return True
    except Exception as e:
        logger.warning("Biopython not available and lazy install failed: %s", e)
    _BIOPYTHON_AVAILABLE = False
    return False


def _which_or_error(cmd: str) -> str | None:
    """Return path to cmd or None. Caller shows a helpful error."""
    return shutil.which(cmd)


def _resolve_path(p: str) -> str:
    """Expand ~ and make absolute."""
    return os.path.abspath(os.path.expanduser(p))


def _detect_format(path: str, hint: str = "auto") -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    aliases = {
        "fa": "fasta",
        "fna": "fasta",
        "ffn": "fasta",
        "faa": "fasta",
        "frn": "fasta",
        "fq": "fastq",
        "gb": "genbank",
        "gbk": "genbank",
    }
    fmt = aliases.get(ext, ext)
    if hint != "auto":
        return hint
    return fmt if fmt else "fasta"


def _run_cmd(cmd: list[str], timeout: int = 3600) -> dict[str, Any]:
    """Run a subprocess, return {returncode, stdout, stderr}."""
    logger.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_PIXI_ENV,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-8000:] if len(proc.stdout) > 8000 else proc.stdout,
        "stderr": proc.stderr[-4000:] if len(proc.stderr) > 4000 else proc.stderr,
    }


def tool_handler[F: Callable[..., str]](func: F) -> F:
    """Catch-all wrapper for tool handlers.

    Handlers with their own try/except keep their error paths; this decorator
    only catches otherwise-unhandled exceptions, logging them and returning
    an {"error": ...} JSON string so a handler never raises into the caller.
    """

    @functools.wraps(func)
    def wrapper(args: dict[str, Any], **kwargs: Any) -> str:
        try:
            return func(args, **kwargs)
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            return json.dumps({"error": f"{func.__name__} failed: {e}"}, ensure_ascii=False)

    return cast(F, wrapper)
