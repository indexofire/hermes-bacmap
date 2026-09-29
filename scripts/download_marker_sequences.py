#!/usr/bin/env python3
"""Batch download marker gene reference sequences from NCBI E-utilities.

Reads the curated gene list from marker_genes_design*.md files,
queries NCBI Nucleotide via efetch for each gene's reference sequence,
and writes a unified FASTA with hermes-bacmap naming convention.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RATE_LIMIT = 0.4
OUT_DIR = ROOT / "data/reference/species"

# ── 基因→参考序列 accession 映射（从文献/GenBank 整理） ──
# 格式: (gene_symbol, pathogen, genbank_acc, description, role)
# role: primary=主靶标 confirm=确认 virulence=毒力 typing=分型 genus=属筛查

MARKER_SEQUENCES = [
    # Salmonella enterica
    ("inva", "Salmonella enterica", "M90846.1", "invasion protein A", "primary"),
    ("rpoD", "Salmonella enterica", "CP026417.1", "RNA polymerase sigma 70", "confirm"),
    ("iroB", "Salmonella enterica", "AF080424.1", "iroB C-glycosyltransferase", "confirm"),
    ("safC", "Salmonella enterica", "FM201984.1", "Salmonella atypical fimbriae usher", "typing"),
    # E. coli / DEC
    ("uida", "Escherichia coli", "NC_000913.3", "beta-D-glucuronidase uidA", "primary"),
    ("lacy", "Escherichia coli", "NC_000913.3", "lactose permease lacY", "primary"),
    ("gada", "Escherichia coli", "NC_000913.3", "glutamate decarboxylase alpha", "confirm"),
    ("stx1", "Escherichia coli", "AF125520.1", "Shiga toxin 1 subunit A", "virulence"),
    ("stx2", "Escherichia coli", "AF125522.1", "Shiga toxin 2 subunit A", "virulence"),
    ("eae", "Escherichia coli", "AF022231.1", "intimin eae", "virulence"),
    # Shigella / EIEC
    ("ipah", "Shigella flexneri", "NC_004337.2", "invasion plasmid antigen H ipaH", "primary"),
    # V. parahaemolyticus
    ("toxr", "Vibrio parahaemolyticus", "NC_004603.1", "toxR regulatory protein", "primary"),
    ("tlh", "Vibrio parahaemolyticus", "M36437.1", "thermolabile hemolysin tlh", "confirm"),
    ("tdh", "Vibrio parahaemolyticus", "M10069.1", "thermostable direct hemolysin", "virulence"),
    ("trh", "Vibrio parahaemolyticus", "U51201.1", "TDH-related hemolysin", "virulence"),
    # V. cholerae
    ("ompw", "Vibrio cholerae", "AF055890.1", "outer membrane protein W", "primary"),
    ("ctxa", "Vibrio cholerae", "X00171.1", "cholera enterotoxin A subunit", "virulence"),
    # V. vulnificus
    ("vvha", "Vibrio vulnificus", "M34462.1", "hemolysin vvhA", "primary"),
    # Campylobacter
    ("mapa", "Campylobacter jejuni", "AL139075.1", "mitogen-associated protein A mapA", "primary"),
    ("hipo", "Campylobacter jejuni", "M97994.1", "hippuricase hipO", "confirm"),
    ("ceue", "Campylobacter coli", "AF321116.1", "iron-uptake receptor ceuE", "primary"),
    ("cadf", "Campylobacter jejuni", "AF033905.1", "fibronectin-binding protein cadF", "confirm"),
    # Listeria
    ("hly", "Listeria monocytogenes", "M24199.1", "listeriolysin O hly", "primary"),
    ("prs", "Listeria monocytogenes", "AF261779.1", "putrescine transport prs", "confirm"),
    ("inlj", "Listeria monocytogenes", "AL592102.1", "internalin J inlJ", "confirm"),
    # Staphylococcus aureus
    ("nuc", "Staphylococcus aureus", "V01281.1", "thermonuclease nuc", "primary"),
    ("fema", "Staphylococcus aureus", "X17688.1", "methicillin resistance femA", "confirm"),
    # Klebsiella
    ("khe", "Klebsiella pneumoniae", "AF072244.1", "hemolysin gene khe", "primary"),
    ("gyrb-kpn", "Klebsiella pneumoniae", "AF318700.1", "DNA gyrase subunit B", "confirm"),
    # Acinetobacter
    ("oxa51", "Acinetobacter baumannii", "AF300835.1", "OXA-51-like carbapenemase", "primary"),
    ("rpob-aba", "Acinetobacter baumannii", "X82164.1", "RNA polymerase beta rpoB", "confirm"),
    # Pseudomonas
    ("ecfx", "Pseudomonas aeruginosa", "AE004091.2", "sigma factor ECF ecfX", "primary"),
    ("gyrb-pae", "Pseudomonas aeruginosa", "L05639.1", "DNA gyrase subunit B", "confirm"),
    # Enterococcus
    ("ddl-ef", "Enterococcus faecalis", "AF181880.1", "D-ala-D-ala ligase ddl", "primary"),
    ("ddl-efm", "Enterococcus faecium", "AF181882.1", "D-ala-D-ala ligase ddl", "primary"),
    # Streptococcus
    ("lyta", "Streptococcus pneumoniae", "M81227.1", "autolysin lytA", "primary"),
    ("psaa", "Streptococcus pneumoniae", "AF030366.1", "manganese transport psaA", "confirm"),
    ("speb", "Streptococcus pyogenes", "M16579.1", "cysteine protease speB", "primary"),
    ("cfb", "Streptococcus agalactiae", "M33317.1", "CAMP factor cfb", "primary"),
    # Neisseria
    ("ctra", "Neisseria meningitidis", "M57681.1", "capsule transport ctrA", "primary"),
    ("sodc", "Neisseria meningitidis", "AF322864.1", "superoxide dismutase C", "confirm"),
    ("pora", "Neisseria gonorrhoeae", "M21289.1", "porin protein A porA", "primary"),
    # Clostridioides difficile
    ("tcda", "Clostridioides difficile", "M30307.1", "toxin A tcdA", "primary"),
    ("tcdb", "Clostridioides difficile", "M19030.1", "toxin B tcdB", "confirm"),
    # Cronobacter
    ("rpob-cs", "Cronobacter sakazakii", "AF064441.1", "RNA polymerase beta rpoB", "primary"),
    # Aeromonas
    ("aera", "Aeromonas hydrophila", "M64716.1", "aerolysin aerA", "primary"),
    ("ahh1", "Aeromonas hydrophila", "S57479.1", "hemolysin ahh1", "confirm"),
    # Yersinia
    ("ail", "Yersinia enterocolitica", "M29945.1", "attachment invasion locus ail", "primary"),
    ("yada", "Yersinia enterocolitica", "X13881.1", "Yersinia adhesin yadA", "confirm"),
    # Bacillus cereus group
    ("nheb", "Bacillus cereus", "Z11886.1", "non-hemolytic enterotoxin B nheB", "virulence"),
    ("ces", "Bacillus cereus", "AF110410.1", "cereulide synthetase ces", "virulence"),
    ("cpa", "Clostridium perfringens", "M24905.1", "alpha toxin cpa/plc", "primary"),
    ("cpe", "Clostridium perfringens", "L43549.1", "enterotoxin cpe", "virulence"),
    # Legionella
    ("mip", "Legionella pneumophila", "M32024.1", "macrophage infectivity potentiator", "primary"),
    ("dota", "Legionella pneumophila", "U91654.1", "DotA type IV secretion", "confirm"),
    # Mycoplasma pneumoniae
    ("p1", "Mycoplasma pneumoniae", "M18622.1", "P1 adhesin protein", "primary"),
    ("cards", "Mycoplasma pneumoniae", "AF390408.1", "CARDS toxin", "confirm"),
    # Chlamydia
    ("ompa-cp", "Chlamydia pneumoniae", "Z31593.1", "major outer membrane protein", "primary"),
    ("ompa-cps", "Chlamydia psittaci", "AY006345.1", "major outer membrane protein", "primary"),
    # Helicobacter pylori
    ("urea", "Helicobacter pylori", "M60398.1", "urease subunit alpha", "primary"),
    ("urec", "Helicobacter pylori", "M60398.1", "urease subunit gamma/ureC", "confirm"),
    ("caga", "Helicobacter pylori", "AB015416.1", "cytotoxin-associated gene A", "virulence"),
    # Bordetella pertussis
    ("is481", "Bordetella pertussis", "M22750.1", "insertion sequence IS481", "primary"),
    ("ptxs1", "Bordetella pertussis", "M13223.1", "pertussis toxin S1 subunit", "confirm"),
    # Corynebacterium diphtheriae
    ("tox", "Corynebacterium diphtheriae", "K01722.1", "diphtheria toxin", "primary"),
    # Haemophilus influenzae
    ("hpd", "Haemophilus influenzae", "U32723.1", "hemoglobin-binding protein D", "primary"),
    # Streptococcus suis
    ("gdh", "Streptococcus suis", "AF363735.1", "glutamate dehydrogenase gdh", "primary"),
    # Burkholderia
    ("bimabp", "Burkholderia pseudomallei", "AF505187.1", "bacterial actin motility BimA(Bp)", "primary"),
    ("tts1", "Burkholderia pseudomallei", "AY089501.1", "type III secretion system 1", "confirm"),
    # Leptospira
    ("lipl32", "Leptospira interrogans", "AF037900.1", "outer membrane protein LipL32", "primary"),
    # Treponema pallidum
    ("tpp47", "Treponema pallidum", "M88726.1", "47kDa membrane lipoprotein", "primary"),
    # Borrelia
    ("ospa", "Borrelia burgdorferi", "M12966.1", "outer surface protein A", "primary"),
    # Plesiomonas
    ("gyrb-ps", "Plesiomonas shigelloides", "AB015801.1", "DNA gyrase subunit B", "primary"),
    # Escherichia albertii
    ("eacf", "Escherichia albertii", "AB074997.1", "E. albertii adherence factor", "primary"),
    # Vibrio fluvialis
    ("toxrf", "Vibrio fluvialis", "AF449565.1", "toxR transcriptional regulator", "primary"),
    # Botulinum
    ("bontA", "Clostridium botulinum", "M30171.1", "botulinum neurotoxin type A", "primary"),
    ("bontB", "Clostridium botulinum", "M81186.1", "botulinum neurotoxin type B", "typing"),
    ("bontE", "Clostridium botulinum", "X62089.1", "botulinum neurotoxin type E", "typing"),
    # Bacillus anthracis
    ("paga", "Bacillus anthracis", "M22504.1", "protective antigen pagA", "primary"),
    ("capb", "Bacillus anthracis", "M64091.1", "capsule biosynthesis capB", "confirm"),
    # Yersinia pestis
    ("caf1", "Yersinia pestis", "X13880.1", "F1 capsule antigen caf1", "primary"),
    ("pla", "Yersinia pestis", "M77367.1", "plasminogen activator pla", "confirm"),
]


def efetch_fasta(accession: str, rettype: str = "fasta") -> str:
    url = f"{EUTILS}/efetch.fcgi?{urllib.parse.urlencode({'db': 'nucleotide', 'id': accession, 'rettype': rettype, 'retmode': 'text'})}"
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-bacmap/0.5"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
            else:
                print(f"  ✗ {accession}: {e}")
                return ""
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DIR / "markers_v2.fasta")
    args = parser.parse_args()

    print(f"downloading {len(MARKER_SEQUENCES)} marker sequences from NCBI...")
    downloaded = 0
    failed = 0

    with args.out.open("w") as out:
        for gene, pathogen, accession, desc, role in MARKER_SEQUENCES:
            time.sleep(RATE_LIMIT)
            raw = efetch_fasta(accession)
            if not raw or not raw.startswith(">"):
                failed += 1
                print(f"  ✗ {gene} ({accession})")
                continue

            lines = raw.strip().splitlines()
            original_header = lines[0][1:]
            sequence = "".join(lines[1:])

            if len(sequence) < 100:
                print(f"  ⚠ {gene} ({accession}): too short ({len(sequence)}bp)")
                failed += 1
                continue

            # 截取合理长度（持家基因太长影响 BLAST 速度）
            max_len = 2200
            seq = sequence[:max_len] if len(sequence) > max_len else sequence

            out.write(f">markers_v2~~~{gene}~~~{accession} {desc} [{pathogen}] role={role}\n")
            for i in range(0, len(seq), 80):
                out.write(seq[i : i + 80] + "\n")
            downloaded += 1
            print(f"  ✓ {gene:15s} {accession:15s} {len(seq):>6d}bp  {pathogen}")

    print(f"\n✓ downloaded: {downloaded}, failed: {failed}")
    print(f"  output: {args.out}")
    return 0 if downloaded > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
