#!/usr/bin/env python3
"""Download the GTDB-Tk R232 reference package (species-id plan C).

Hard gates per docs/plans/species-id/03-gtdbtk-checkm2.md: classify needs
>=140 GB RAM (bacterial split tree) and ~220 GB free disk (tarball +
extracted + pplacer scratch).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import download_database  # noqa: E402

URLS = [
    "https://data.gtdb.aau.ecogenomic.org/releases/release232/232.0/auxillary_files/gtdbtk_package/full_package/gtdbtk_r232_data.tar.gz",
    "https://data.gtdb.ecogenomic.org/releases/release232/232.0/auxillary_files/gtdbtk_package/full_package/gtdbtk_r232_data.tar.gz",
    "https://data.ace.uq.edu.au/public/gtdb/data/releases/release232/232.0/auxillary_files/gtdbtk_package/full_package/gtdbtk_r232_data.tar.gz",
]
MD5 = "25a59e0352b1fd150c589f56559767d4"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data/db"))
    args = parser.parse_args(argv)

    dest = download_database(
        name="gtdbtk_r232",
        urls=URLS,
        dest_dir=args.data_root / "gtdbtk",
        expected_md5=MD5,
        expected_size_gb=98.0,
        min_free_gb=220.0,
        min_ram_gb=140.0,
    )
    print(f"GTDB-Tk R232 installed at {dest}")
    print("解压后设置: export GTDBTK_DATA_PATH=<解压目录>/gtdbtk_r232_data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
