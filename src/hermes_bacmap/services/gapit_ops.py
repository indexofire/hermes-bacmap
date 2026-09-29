"""gapit database operations — custom screening database builder.

Wraps `gapit db build <name> <fasta>` (abricate ~~~ / gapit| headers,
nucl/prot auto-detect) so the agent can deploy validated novel markers as
screenable databases. The resulting directory lives under the gapit
datadir and is immediately usable by gapit screen / bio_gene_scan.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from ..config import pixi_path, which

_RECORDS_RE = re.compile(r"(\d+)\s+record")


def db_build(
    name: str,
    fasta: Path,
    description: str = "",
    dbtype: str = "",
    datadir: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    fasta = Path(fasta)
    if not fasta.exists():
        raise FileNotFoundError(f"marker FASTA not found: {fasta}")

    bin_path = which("gapit")
    if not bin_path:
        raise RuntimeError("gapit not found in PATH. Install: pixi add 'gapit>=0.2'")

    cmd = [bin_path, "db", "build", name, str(fasta)]
    if description:
        cmd += ["--description", description]
    if dbtype:
        cmd += ["--dbtype", dbtype]
    if datadir is not None:
        cmd += ["--datadir", str(datadir)]
    if force:
        cmd += ["--force"]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        env={"PATH": pixi_path()},
    )
    if result.returncode != 0:
        raise RuntimeError(f"gapit db build failed: {result.stderr.strip()[:500]}")

    db_path = (datadir or _default_datadir()) / name
    if not db_path.exists():
        db_path = Path.home() / ".local" / "share" / "gapit" / "db" / name

    m = _RECORDS_RE.search(result.stdout)
    return {
        "db_name": name,
        "db_path": str(db_path),
        "records": int(m.group(1)) if m else 0,
        "description": description,
    }


def _default_datadir() -> Path:
    import os

    env = os.environ.get("GAPIT_DATADIR")
    if env:
        return Path(env)
    return Path.home() / ".local" / "share" / "gapit" / "db"
