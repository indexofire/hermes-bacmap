#!/usr/bin/env python3
"""Download the community-maintained RefSeq Mash sketch (species-id A-instant).

Upstream: erinyoung/update_mash_dist, auto-released per RefSeq version on
Zenodo. Re-running this script upgrades the sketch to the latest RefSeq.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import download_database  # noqa: E402

URLS = [
    "https://zenodo.org/records/22664519/files/RefSeqSketches_237.msh.gz",
]
MD5 = "dee53b23af3ab120333f9eb1b95ae60f"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data/db"))
    args = parser.parse_args(argv)

    download_database(
        name="mash_refseq",
        urls=URLS,
        dest_dir=args.data_root / "mash_refseq",
        expected_md5=MD5,
        expected_size_gb=0.16,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
