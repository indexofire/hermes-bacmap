#!/usr/bin/env python3
"""Validate species identification methods against the downloaded truth table.

Truth source: tests/fixtures/validation_genomes/manifest.tsv (built by
download_validation_genomes.py from NCBI Pathogen-tracked taxa). Each row's
NCBI taxonomy is the expected answer; targets must be identified as one of
our supported pathogens, negatives must NOT be claimed as one.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_TARGET_KEYWORDS = {
    "Salmonella": ["salmonella"],
    "E.coli/Shigella": ["escherichia coli", "shigella", "dec"],
    "V.parahaemolyticus": ["parahaemolyticus"],
}
_ALL_TARGET_KEYWORDS = [k for kws in _TARGET_KEYWORDS.values() for k in kws]


def _norm(s: str) -> str:
    return s.lower().replace("_", " ").replace(".", "")


def judge(expected: str, species: str, role: str) -> bool:
    got = _norm(species)
    if role == "target":
        return any(k in got for k in _TARGET_KEYWORDS[expected])
    return not any(k in got for k in _ALL_TARGET_KEYWORDS)


def _run_marker(fna: str) -> str:
    from hermes_bacmap.analysis.species_identifier import identify

    return identify(fna).species


def _run_mash(fna: str) -> str:
    from hermes_bacmap.analysis.ani_identifier import identify_by_ani

    return identify_by_ani(fna, "mash_refseq").result["species"]


def _run_panel(fna: str) -> str:
    from hermes_bacmap.analysis.ani_identifier import identify_by_ani

    return identify_by_ani(fna, "panel").result["species"]


_RUNNERS = {"marker": _run_marker, "mash_refseq": _run_mash, "panel": _run_panel}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "tests/fixtures/validation_genomes/manifest.tsv",
    )
    parser.add_argument("--methods", nargs="*", default=["marker", "mash_refseq"])
    args = parser.parse_args(argv)

    with args.manifest.open() as fh:
        rows = [r for r in csv.DictReader(fh, delimiter="\t") if Path(r["fna"]).is_file()]

    print(f"genomes: {len(rows)}  methods: {args.methods}\n")
    failures = 0
    for method in args.methods:
        runner = _RUNNERS[method]
        correct = 0
        misses = []
        for row in rows:
            try:
                species = runner(row["fna"])
            except Exception as e:  # noqa: BLE001
                species = f"ERROR: {e}"
            ok = judge(row["expected"], species, row["role"])
            correct += ok
            if not ok:
                misses.append((row["accession"], row["expected"], species))
        failures += len(misses)
        print(f"[{method}] accuracy: {correct}/{len(rows)} ({correct / len(rows):.0%})")
        for accession, expected, species in misses:
            print(f"  MISS {accession}: expected={expected} got={species!r}")
        print()

    print("verdict:", "PASS" if failures == 0 else f"{failures} miss(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
