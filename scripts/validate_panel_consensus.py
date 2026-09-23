#!/usr/bin/env python3
"""Batch cross-validate all panel genomes using three independent methods.

For each of the ~1644 bacterial genomes in the panel:
1. skani panel mode — ANI against the panel itself (self-hit should dominate)
2. mash RefSeq — whole-genome MinHash distance to all RefSeq sketches
3. marker genes — BLAST against invA/uidA/ipaH/toxR/tlh markers

Each method's species call is compared against the NCBI organism label
(from metadata.tsv). Cross-method agreement is scored.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_bacmap.config import SPECIES_DB_DIR  # noqa: E402

PANEL = SPECIES_DB_DIR / "refseq_panel"
GENOMES = PANEL / "genomes"
SKANI_BIN = str(ROOT / ".pixi/envs/default/bin/skani")
SKANI_DB = str(PANEL / "panel.sketch")
MASH_BIN = str(ROOT / ".pixi/envs/default/bin/mash")
MASH_DB = str(SPECIES_DB_DIR / "mash_refseq" / "mash.msh")
BLASTN_BIN = str(ROOT / ".pixi/envs/default/bin/blastn")
MARKERS_DB = str(ROOT / "data/reference/species_markers_blastdb")

KNOWN_TARGETS = {
    "salmonella": "Salmonella",
    "escherichia": "E.coli",
    "shigella": "Shigella/EIEC",
    "parahaemolyticus": "V.parahaemolyticus",
}


def genus_species(name: str) -> str:
    parts = name.replace("_", " ").split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return parts[0] if parts else ""


def run_skani(fna: str) -> tuple[str, float]:
    result = subprocess.run(
        [SKANI_BIN, "search", fna, "-d", SKANI_DB],
        capture_output=True, text=True, timeout=120,
    )
    lines = result.stdout.strip().splitlines()
    if len(lines) < 2:
        return ("", 0.0)
    cols = lines[1].split("\t")
    try:
        ani = float(cols[2])
    except (ValueError, IndexError):
        return ("", 0.0)
    ref_name = cols[5] if len(cols) > 5 else cols[0]
    return (ref_name, ani)


def run_mash(fna: str) -> tuple[str, float]:
    result = subprocess.run(
        [MASH_BIN, "dist", MASH_DB, fna],
        capture_output=True, text=True, timeout=120,
    )
    best_name, best_sim = "", 0.0
    for ln in result.stdout.splitlines():
        cols = ln.split("\t")
        if len(cols) >= 3:
            try:
                sim = 1.0 - float(cols[2])
            except ValueError:
                continue
            if sim > best_sim:
                best_sim = sim
                best_name = cols[0]
    return (best_name, best_sim)


def run_marker(fna: str) -> str:
    result = subprocess.run(
        [BLASTN_BIN, "-query", fna, "-db", MARKERS_DB,
         "-outfmt", "6 sseqid pident qcovs", "-evalue", "1e-50",
         "-word_size", "28", "-num_threads", "1"],
        capture_output=True, text=True, timeout=120,
    )
    hits = {}
    for ln in result.stdout.splitlines():
        cols = ln.split("\t")
        if len(cols) >= 3:
            gene = cols[0].split("~~~")[1].lower() if "~~~" in cols[0] else cols[0].lower()
            try:
                ident = float(cols[1])
                cov = float(cols[2])
            except ValueError:
                continue
            if ident >= 85 and cov >= 30:
                if gene not in hits or ident > hits[gene]:
                    hits[gene] = ident

    if not hits:
        return "Unknown"
    for gene in ["inva", "ipah", "toxr", "tlh", "uida"]:
        if gene in hits:
            if gene == "inva":
                return "Salmonella"
            if gene == "ipah":
                return "Shigella/EIEC"
            if gene in ("toxr", "tlh"):
                return "V.parahaemolyticus"
            if gene == "uida":
                return "E.coli"
    return "Unknown"


def strip_accession(name: str) -> str:
    return re.sub(r'^[A-Z]{2}_\d+\.\d+\s+', '', name)


def match_expected(expected: str, called: str) -> str:
    if not called or not expected:
        return "no_call"
    called = strip_accession(called)
    e, c = expected.lower(), called.lower()
    e_words = e.split()
    c_words = c.replace("_", " ").split()
    e_gen = e_words[0] if e_words else ""
    c_gen = c_words[0] if c_words else ""

    if e_gen and c_gen and (e_gen in c_gen or c_gen in e_gen):
        if len(e_words) >= 2 and len(c_words) >= 2:
            if e_words[1] in " ".join(c_words[1:3]):
                return "species_match"
        return "genus_match"
    for target_kw in KNOWN_TARGETS:
        if target_kw in e and target_kw in c:
            return "species_match"
    return "mismatch"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PANEL / "consensus_validation.tsv")
    parser.add_argument("--limit", type=int, default=0, help="Limit for smoke test (0=all)")
    args = parser.parse_args()

    metadata = {}
    with (PANEL / "metadata.tsv").open() as fh:
        for rec in csv.DictReader(fh, delimiter="\t"):
            metadata[rec["fna"]] = rec["species"]

    fnas = sorted(GENOMES.glob("*_genomic.fna"))
    if args.limit:
        fnas = fnas[: args.limit]
    print(f"validating {len(fnas)} genomes (3 methods)...")

    start = time.time()
    agree_3 = 0
    agree_2 = 0
    mismatch = 0
    results = []

    with args.out.open("w") as fh:
        fh.write("fna\tncbi_organism\tskani_ani\tskani_ref\tmash_sim\tmash_top\t"
                 "marker_call\tskani_match\tmash_match\tmarker_match\tconsensus\n")
        for i, fna in enumerate(fnas):
            org = metadata.get(fna.name, "")
            expected = genus_species(org)

            sk_ref, sk_ani = run_skani(str(fna))
            m_top, m_sim = run_mash(str(fna))
            marker = run_marker(str(fna))

            sk_match = match_expected(expected, sk_ref)
            m_match = match_expected(expected, m_top)
            mk_match = "n/a" if marker == "Unknown" else match_expected(expected, marker)

            matches = [m for m in (sk_match, m_match) if m in ("species_match", "genus_match")]
            n_agree = len(matches)
            consensus = "agree" if n_agree == 2 else "partial" if n_agree == 1 else "disagree"

            if n_agree == 2:
                agree_3 += 1
            elif n_agree == 1:
                agree_2 += 1
            else:
                mismatch += 1

            fh.write(f"{fna.name}\t{org}\t{sk_ani:.2f}\t{sk_ref[:50]}\t"
                     f"{m_sim:.4f}\t{m_top[:50]}\t{marker}\t"
                     f"{sk_match}\t{m_match}\t{mk_match}\t{consensus}\n")

            if (i + 1) % 50 == 0:
                elapsed = time.time() - start
                eta = elapsed / (i + 1) * (len(fnas) - i - 1)
                print(f"  {i+1}/{len(fnas)} ({(i+1)/len(fnas):.0%}) ETA {eta/60:.0f}min "
                      f"agree:{agree_3} partial:{agree_2} disagree:{mismatch}")

    elapsed = time.time() - start
    print(f"\ndone: {len(fnas)} genomes in {elapsed/60:.1f} min")
    print(f"  agree (2/2):    {agree_3} ({agree_3/len(fnas):.0%})")
    print(f"  partial (1/2):  {agree_2} ({agree_2/len(fnas):.0%})")
    print(f"  disagree (0/2): {mismatch} ({mismatch/len(fnas):.0%})")
    print(f"  report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
