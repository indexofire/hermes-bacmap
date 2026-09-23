#!/usr/bin/env python3
"""Check within-species genome diversity using skani pairwise ANI.

For each species with >1 genome in the panel, computes pairwise ANI.
Genomes with ANI >= 99.99% to another genome are flagged as "clonal"
(redundant, replace recommended). This is a proxy for MUMmer SNP<500.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data/db/refseq_panel"
GENOMES = PANEL / "genomes"
SKANI = str(ROOT / ".pixi/envs/default/bin/skani")

CLONAL_ANI = 99.99


def main() -> int:
    metadata = {}
    with (PANEL / "metadata.tsv").open() as fh:
        for rec in csv.DictReader(fh, delimiter="\t"):
            metadata[rec["fna"]] = rec["species"]

    by_species: dict[str, list[str]] = {}
    for fna_name, species in metadata.items():
        words = species.split()
        if len(words) >= 2:
            binomial = f"{words[0]} {words[1]}"
        else:
            binomial = species
        by_species.setdefault(binomial, []).append(fna_name)

    print(f"species with >1 genome: {sum(1 for v in by_species.values() if len(v) > 1)}")
    print(f"CLONAL threshold: ANI >= {CLONAL_ANI}%\n")

    redundant = []
    total_pairs = 0
    clonal_pairs = 0

    for species, fnames in sorted(by_species.items()):
        if len(fnames) < 2:
            continue

        for i in range(len(fnames)):
            for j in range(i + 1, len(fnames)):
                f1 = GENOMES / fnames[i]
                f2 = GENOMES / fnames[j]
                if not f1.exists() or not f2.exists():
                    continue

                total_pairs += 1
                result = subprocess.run(
                    [SKANI, "dist", str(f1), str(f2)],
                    capture_output=True, text=True, timeout=60,
                )
                lines = result.stdout.strip().splitlines()
                if len(lines) < 2:
                    continue

                cols = lines[1].split("\t")
                try:
                    ani = float(cols[2])
                except (ValueError, IndexError):
                    continue

                if ani >= CLONAL_ANI:
                    clonal_pairs += 1
                    redundant.append((species, fnames[i], fnames[j], ani))

    print(f"total pairs checked: {total_pairs}")
    print(f"clonal pairs (ANI >= {CLONAL_ANI}%): {clonal_pairs}")
    print(f"unique pairs: {total_pairs - clonal_pairs}")

    if redundant:
        print(f"\n=== Clonal genome pairs (replace recommended) ===")
        for species, f1, f2, ani in redundant:
            print(f"  {species:30s}  {f1[:30]:30s} ↔ {f2[:30]:30s}  ANI={ani:.4f}%")

        out = PANEL / "clonal_genomes.tsv"
        with out.open("w") as fh:
            fh.write("species\tgenome1\tgenome2\tani\n")
            for species, f1, f2, ani in redundant:
                fh.write(f"{species}\t{f1}\t{f2}\t{ani:.4f}\n")
        print(f"\nReport: {out}")
    else:
        print("\n✓ No clonal pairs — all genomes provide unique diversity")

    return 0


if __name__ == "__main__":
    sys.exit(main())
