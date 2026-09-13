#!/usr/bin/env python3
"""Install the CheckM2 DIAMOND database (species-id plan C).

Prefers `checkm2 database --download` (available with the pixi taxonomic
feature env); falls back to the Zenodo record for manual download.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import download_database  # noqa: E402

ZENODO_URLS = [
    "https://zenodo.org/record/14897628/files/uniref100.KO.1.dmnd",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data/db"))
    args = parser.parse_args(argv)

    dest_dir = args.data_root / "checkm2"
    if shutil.which("checkm2"):
        result = subprocess.run(["checkm2", "database", "--download", "--path", str(dest_dir)])
        if result.returncode == 0:
            print(f"CheckM2 database installed at {dest_dir}")
            return 0

    download_database(
        name="checkm2",
        urls=ZENODO_URLS,
        dest_dir=dest_dir,
        expected_size_gb=3.0,
    )
    print("设置: export CHECKM2DB=<目录>/uniref100.KO.1.dmnd")
    return 0


if __name__ == "__main__":
    sys.exit(main())
