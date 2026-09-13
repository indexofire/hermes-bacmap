#!/usr/bin/env python3
"""Download the official skani pre-sketched GTDB R226 database (species-id A-full)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import download_database  # noqa: E402

URLS = [
    "http://faust.compbio.cs.cmu.edu/skani-files/skani_gtdb_r226-v0.3.tar.gz",
]

TAXONOMY_URLS = [
    "https://data.gtdb.ecogenomic.org/releases/release226/226.0/genomic_files_all/bac120_taxonomy_r226.tsv.gz",
    "https://data.ace.uq.edu.au/public/gtdb/data/releases/release226/226.0/genomic_files_all/bac120_taxonomy_r226.tsv.gz",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data/db"))
    args = parser.parse_args(argv)

    dest = download_database(
        name="skani_gtdb",
        urls=URLS,
        dest_dir=args.data_root / "skani_gtdb",
        expected_size_gb=30.0,
        min_free_gb=110.0,
    )
    taxa = args.data_root / "skani_gtdb" / "bac120_taxonomy_r226.tsv"
    if not taxa.exists():
        download_database(
            name="skani_gtdb_taxonomy",
            urls=TAXONOMY_URLS,
            dest_dir=args.data_root / "skani_gtdb_taxonomy",
            expected_size_gb=0.1,
        )
    print(f"skani GTDB R226 installed at {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
