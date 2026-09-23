#!/usr/bin/env python3
"""Batch audit of panel genomes: species cross-validation + N content check.

For each of the ~2495 panel genomes:
1. Count N bases (ambiguous calls)
2. Run mash_refseq identification (fastest whole-genome method)
3. Compare result's top hit against the genome's own NCBI label
   (self-hit should be distance ~0; mismatches indicate label or data issues)

Writes: data/db/refseq_panel/audit_report.tsv + audit_summary.txt
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_bacmap.config import SPECIES_DB_DIR  # noqa: E402

PANEL = SPECIES_DB_DIR / "refseq_panel"
MASH_BIN = str(ROOT / ".pixi/envs/default/bin/mash")
MASH_DB = str(SPECIES_DB_DIR / "mash_refseq" / "mash.msh")


def count_n(fna: Path) -> int:
    n = 0
    with fna.open() as fh:
        for line in fh:
            if not line.startswith(">"):
                n += line.strip().upper().count("N")
    return n


def mash_self_rank(fna: Path) -> tuple[str, float, float, int]:
    """Returns (top_hit_name, similarity, second_similarity, total_hits)."""
    result = subprocess.run(
        [MASH_BIN, "dist", MASH_DB, str(fna)],
        capture_output=True, text=True, timeout=120,
    )
    rows = []
    for ln in result.stdout.splitlines():
        cols = ln.split("\t")
        if len(cols) >= 3:
            try:
                rows.append((cols[0], 1.0 - float(cols[2])))
            except ValueError:
                continue
    rows.sort(key=lambda r: -r[1])
    if not rows:
        return ("", 0.0, 0.0, 0)
    return (rows[0][0], rows[0][1], rows[1][1] if len(rows) > 1 else 0.0, len(rows))


def genus_of(name: str) -> str:
    parts = name.replace("_", " ").split()
    return parts[0] if parts else ""


def main() -> int:
    genomes = sorted((PANEL / "genomes").glob("*_genomic.fna"))
    print(f"auditing {len(genomes)} genomes...")

    report = PANEL / "audit_report.tsv"
    summary_path = PANEL / "audit_summary.txt"

    n_with_n = 0
    mismatches = 0
    n_replace = 0
    start = time.time()

    with report.open("w") as fh:
        fh.write("accession\tn_bases\ttop_hit\tsim\tsecond_sim\tgenus_match\taction\n")
        for i, fna in enumerate(genomes):
            acc = fna.name.split("_ASM")[0]
            n_count = count_n(fna)
            top, sim, sim2, hits = mash_self_rank(fna)

            self_genus = genus_of(acc)
            hit_genus = genus_of(top)
            genus_match = "Y" if self_genus == hit_genus else "N"

            action = ""
            if n_count > 0:
                action = "N_CONTENT"
                n_with_n += 1
                n_replace += 1
            elif genus_match == "N":
                action = "LABEL_MISMATCH"
                mismatches += 1
            elif sim < 0.95:
                action = "LOW_SELF_SIM"

            fh.write(
                f"{acc}\t{n_count}\t{top}\t{sim:.4f}\t{sim2:.4f}\t"
                f"{genus_match}\t{action}\n"
            )

            if (i + 1) % 100 == 0:
                elapsed = time.time() - start
                eta = elapsed / (i + 1) * (len(genomes) - i - 1)
                print(
                    f"  {i + 1}/{len(genomes)} "
                    f"({(i + 1) / len(genomes):.0%}) "
                    f"ETA {eta / 60:.0f}min "
                    f"N:{n_with_n} mismatch:{mismatches}"
                )

    elapsed = time.time() - start
    lines = [
        f"Panel genome audit: {len(genomes)} genomes",
        f"Time: {elapsed / 60:.1f} min",
        f"",
        f"Results:",
        f"  N-containing genomes: {n_with_n} (replace recommended)",
        f"  Genus label mismatches: {mismatches}",
        f"  Low self-similarity (<0.95): see report",
        f"  Replace candidates total: {n_replace}",
        f"",
        f"Action breakdown:",
        f"  N_CONTENT — genome has ambiguous N bases, replace with cleaner assembly",
        f"  LABEL_MISMATCH — mash top hit genus differs from NCBI label genus",
        f"  LOW_SELF_SIM — mash best hit <0.95 similarity (possible contamination)",
    ]
    summary_path.write_text("\n".join(lines) + "\n")
    print(f"\ndone: {len(genomes)} genomes in {elapsed / 60:.1f} min")
    print(f"  N-containing: {n_with_n}")
    print(f"  Genus mismatches: {mismatches}")
    print(f"Report: {report}")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
