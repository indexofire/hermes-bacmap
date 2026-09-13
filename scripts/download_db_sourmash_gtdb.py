#!/usr/bin/env python3
"""Download sourmash GTDB RS226 signatures + lineage taxonomy (species-id plan B)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import download_database  # noqa: E402

BASE = "https://farm.cse.ucdavis.edu/~ctbrown/sourmash-db.new/gtdb-rs226"

SIGNATURE_URLS = [f"{BASE}/gtdb-reps-rs226-k31.dna.zip"]
LINEAGE_URLS = [f"{BASE}/gtdb-rs226.lineages.csv"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data/db"))
    args = parser.parse_args(argv)

    dest = download_database(
        name="sourmash_gtdb",
        urls=SIGNATURE_URLS,
        dest_dir=args.data_root / "sourmash_gtdb",
        expected_size_gb=3.7,
        min_free_gb=8.0,
    )
    download_database(
        name="sourmash_gtdb_lineages",
        urls=LINEAGE_URLS,
        dest_dir=args.data_root / "sourmash_gtdb_lineages",
        expected_size_gb=0.05,
    )
    print(f"sourmash GTDB RS226 installed at {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
