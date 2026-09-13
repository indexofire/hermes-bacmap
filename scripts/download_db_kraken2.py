#!/usr/bin/env python3
"""Build the custom kraken2/bracken library (species-id plan D).

Reuses the A-mini RefSeq panel FASTAs as the microbial backbone, adds
GRCh38 (host scrubbing) and UniVec_Core (vector contamination), then runs
kraken2-build + bracken-build.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

GRCH38_URLS = [
    "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/001/405/GCF_000001405.40_GRCh38.p14/GCF_000001405.40_GRCh38.p14_genomic.fna.gz",
]

STEPS = (
    ["kraken2-build", "--download-taxonomy", "--db", "{db}"],
    ["kraken2-build", "--download-library", "UniVec_Core", "--db", "{db}"],
    ["kraken2-build", "--add-to-library", "{human}", "--db", "{db}"],
    ["kraken2-build", "--add-to-library", "{panel}", "--db", "{db}"],
    [
        "kraken2-build",
        "--build",
        "--kmer-len",
        "35",
        "--minimizer-len",
        "31",
        "--threads",
        "{threads}",
        "--db",
        "{db}",
    ],
    ["bracken-build", "-d", "{db}", "-k", "35", "-l", "150", "-t", "{threads}"],
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data/db"))
    parser.add_argument("--threads", type=int, default=32)
    args = parser.parse_args(argv)

    db = args.data_root / "kraken2_custom"
    panel = args.data_root / "refseq_panel" / "genomes"
    if not panel.is_dir():
        print("先运行 download_db_refseq_panel.py（kraken2 库复用面板基因组）")
        return 2

    human = args.data_root / "kraken2_src" / "GRCh38_genomic.fna.gz"
    human.parent.mkdir(parents=True, exist_ok=True)
    if not human.exists():
        for url in GRCH38_URLS:
            if subprocess.run(["wget", "-c", "-O", str(human), url]).returncode == 0:
                break
        else:
            print("GRCh38 下载失败（--mirror 可改源）")
            return 1

    fmt = {"db": str(db), "human": str(human), "panel": str(panel), "threads": str(args.threads)}
    for step in STEPS:
        cmd = [p.format(**fmt) for p in step]
        print(f"$ {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
    print(f"kraken2 custom library installed at {db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
