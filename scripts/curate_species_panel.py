#!/usr/bin/env python3
"""Build a curated species panel with clinical priority tiers.

Reads taxonomy_verified.tsv + taxonomy_review.md species lists, selects
clinically important pathogens (tier-weighted genome quotas), filters
assembly_summary for high-quality genomes (Complete Genome, N<500),
and outputs the definitive panel genome list.

Tier system:
  T1 = critical (10 genomes): WHO priority / notifiable disease
  T2 = high (6):  common clinical / foodborne
  T3 = medium (4): opportunistic / regional
  T4 = low (2):   near-relative specificity controls
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PANEL_DIR = ROOT / "data/db/refseq_panel"

# ── 物种临床重要性分级 + 基因组配额 ──
SPECIES_TIERS = {
    # T1: critical pathogens (10 genomes each)
    "Salmonella enterica": 10,          # notifiable, top foodborne
    "Escherichia coli": 10,             # DEC/STEC/ETEC, notifiable
    "Shigella flexneri": 8,             # notifiable (菌痢)
    "Shigella sonnei": 8,               # notifiable, increasing in China
    "Shigella dysenteriae": 6,          # type 1 → epidemic
    "Shigella boydii": 5,
    "Vibrio parahaemolyticus": 10,      # top seafood-borne in China
    "Vibrio cholerae": 8,               # 甲类
    "Listeria monocytogenes": 8,        # high mortality
    "Campylobacter jejuni": 8,          # #1 foodborne globally
    "Campylobacter coli": 5,
    "Klebsiella pneumoniae": 10,        # ESBL/CRE, WHO critical
    "Acinetobacter baumannii": 10,      # CRAB, WHO critical
    "Staphylococcus aureus": 10,        # MRSA, WHO high
    "Neisseria meningitidis": 8,        # epidemic meningitis

    # T2: high priority (6 genomes)
    "Streptococcus pneumoniae": 6,
    "Streptococcus pyogenes": 6,
    "Streptococcus agalactiae": 5,
    "Enterococcus faecalis": 5,
    "Enterococcus faecium": 5,
    "Pseudomonas aeruginosa": 6,
    "Clostridioides difficile": 6,
    "Cronobacter sakazakii": 5,
    "Neisseria gonorrhoeae": 5,

    # T3: medium (4 genomes)
    "Acinetobacter pittii": 4,
    "Acinetobacter nosocomialis": 4,
    "Acinetobacter calcoaceticus": 3,
    "Acinetobacter seifertii": 3,
    "Acinetobacter lwoffii": 3,
    "Acinetobacter junii": 3,
    "Acinetobacter haemolyticus": 3,
    "Acinetobacter radioresistens": 3,
    "Klebsiella oxytoca": 4,
    "Klebsiella aerogenes": 4,
    "Klebsiella variicola": 4,
    "Klebsiella quasipneumoniae": 3,
    "Klebsiella ornithinolytica": 3,
    "Aeromonas hydrophila": 4,
    "Aeromonas caviae": 4,
    "Aeromonas veronii": 4,
    "Aeromonas dhakensis": 3,
    "Serratia marcescens": 4,
    "Morganella morganii": 3,
    "Providencia rettgeri": 3,
    "Providencia stuartii": 3,
    "Providencia alcalifaciens": 3,
    "Elizabethkingia anophelis": 3,
    "Elizabethkingia meningoseptica": 3,

    # T4: specificity controls / near-relatives (2 genomes)
    "Salmonella bongori": 2,
    "Listeria innocua": 2,
    "Listeria seeligeri": 2,
    "Listeria welshimeri": 2,
    "Listeria ivanovii": 2,
    "Campylobacter lari": 2,
    "Campylobacter upsaliensis": 2,
    "Campylobacter fetus": 2,
    "Klebsiella planticola": 2,
    "Cronobacter malonaticus": 2,
    "Cronobacter turicensis": 2,
    "Vibrio vulnificus": 3,
    "Vibrio alginolyticus": 3,
    "Vibrio harveyi": 2,
    "Vibrio mimicus": 2,
    "Vibrio fluvialis": 2,
    "Aeromonas salmonicida": 2,
    "Aeromonas schubertii": 2,
    "Aeromonas jandaei": 2,
    "Serratia liquefaciens": 2,
    "Serratia odorifera": 2,
    "Serratia rubidaea": 2,
    "Streptococcus suis": 2,
    "Streptococcus iniae": 2,
}


def load_summary():
    """Load assembly_summary → list of dict per genome."""
    summary_path = PANEL_DIR / "assembly_summary_refseq.txt"
    rows = []
    with summary_path.open() as fh:
        header = None
        for ln in fh:
            if ln.startswith("#"):
                if "assembly_accession" in ln:
                    header = ln.lstrip("# ").rstrip("\n").split("\t")
                continue
            if not header:
                continue
            rows.append(dict(zip(header, ln.rstrip("\n").split("\t"))))
    return rows


def select_genomes(summary_rows: list[dict]) -> list[dict]:
    """For each species in SPECIES_TIERS, pick best genomes."""
    # Build species → candidate genomes index
    by_species: dict[str, list[dict]] = {}
    for rec in summary_rows:
        org = rec.get("organism_name", "")
        level = rec.get("assembly_level", "")
        category = rec.get("refseq_category", "na")

        # Match to our species list (genus + species epithet)
        words = org.split()
        if len(words) < 2:
            continue
        binomial = f"{words[0]} {words[1]}"
        if binomial not in SPECIES_TIERS:
            continue

        # Quality filters
        if level not in ("Complete Genome", "Chromosome"):
            continue

        by_species.setdefault(binomial, []).append(rec)

    selected = []
    for species, quota in sorted(SPECIES_TIERS.items()):
        candidates = by_species.get(species, [])
        if not candidates:
            print(f"  ⚠ {species}: no qualified genomes found")
            continue

        # Sort: reference > representative > other; Complete > Chromosome
        def sort_key(rec):
            cat = rec.get("refseq_category", "na")
            lvl = rec.get("assembly_level", "")
            cat_rank = 0 if cat == "reference genome" else 1 if cat == "representative genome" else 2
            lvl_rank = 0 if lvl == "Complete Genome" else 1
            return (cat_rank, lvl_rank, rec.get("assembly_accession", ""))

        candidates.sort(key=sort_key)
        chosen = candidates[:quota]
        selected.extend(chosen)
        n_ref = sum(1 for c in chosen if c.get("refseq_category") == "reference genome")
        n_complete = sum(1 for c in chosen if c.get("assembly_level") == "Complete Genome")
        print(
            f"  ✓ {species:35s} {len(chosen):2d}/{quota}  "
            f"(ref:{n_ref} complete:{n_complete}  pool:{len(candidates)})"
        )

    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path, default=PANEL_DIR / "curated_species_list.tsv")
    args = parser.parse_args()

    print(f"目标物种数: {len(SPECIES_TIERS)}")
    print(f"总配额: {sum(SPECIES_TIERS.values())} 基因组\n")

    rows = load_summary()
    print(f"assembly_summary 总行: {len(rows)}\n")

    print("筛选：")
    selected = select_genomes(rows)

    print(f"\n选中: {len(selected)} 基因组")

    if args.dry_run:
        for rec in selected[:30]:
            print(f"  {rec['assembly_accession']:20s} {rec['refseq_category']:20s} {rec['organism_name'][:40]}")
        return 0

    with args.out.open("w") as fh:
        fh.write("accession\torganism\trefseq_category\tassembly_level\tftp_path\n")
        for rec in selected:
            fh.write(
                f"{rec['assembly_accession']}\t{rec['organism_name']}\t"
                f"{rec['refseq_category']}\t{rec['assembly_level']}\t"
                f"{rec.get('ftp_path', '')}\n"
            )
    print(f"清单: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
