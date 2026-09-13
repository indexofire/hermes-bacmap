#!/usr/bin/env python3
"""Download validation genomes from NCBI Datasets for species-ID validation.

Pathogen scope follows the NCBI Pathogen Detection tracked organism list
(https://www.ncbi.nlm.nih.gov/pathogens/organisms/ — the table is
JS-rendered; the group names below are those tracked groups). Defaults:

- targets: the 3 NCBI groups covering our 4 supported pathogens
  (Salmonella enterica; Escherichia coli/Shigella; Vibrio parahaemolyticus)
- negatives: near-neighbour groups from the same list, used as specificity
  controls (correct answer = NOT one of our 4 pathogens)

For each taxon the script selects RefSeq reference/representative assemblies
(complete/chromosome level), downloads FASTA via the dehydrated/rehydrate
path, and writes a manifest TSV that doubles as the validation truth table
(accession → expected species label → role).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = str(ROOT / ".pixi/envs/default/bin/datasets")

DEFAULT_PER_TAXON = 6

PATHOGENS: list[dict[str, str]] = [
    {"taxon": "Salmonella enterica", "expected": "Salmonella", "role": "target"},
    {"taxon": "Escherichia coli", "expected": "E.coli/Shigella", "role": "target"},
    {"taxon": "Shigella", "expected": "E.coli/Shigella", "role": "target"},
    {"taxon": "Vibrio parahaemolyticus", "expected": "V.parahaemolyticus", "role": "target"},
    {"taxon": "Vibrio alginolyticus", "expected": "V.alginolyticus_negative", "role": "negative"},
    {"taxon": "Vibrio harveyi", "expected": "V.harveyi_negative", "role": "negative"},
    {"taxon": "Vibrio vulnificus", "expected": "V.vulnificus_negative", "role": "negative"},
    {"taxon": "Vibrio cholerae", "expected": "V.cholerae_negative", "role": "negative"},
    {"taxon": "Klebsiella pneumoniae", "expected": "K.pneumoniae_negative", "role": "negative"},
    {"taxon": "Listeria monocytogenes", "expected": "L.monocytogenes_negative", "role": "negative"},
    {"taxon": "Campylobacter jejuni", "expected": "C.jejuni_negative", "role": "negative"},
    {"taxon": "Cronobacter sakazakii", "expected": "C.sakazakii_negative", "role": "negative"},
    {"taxon": "Staphylococcus aureus", "expected": "S.aureus_negative", "role": "negative"},
    {"taxon": "Pseudomonas aeruginosa", "expected": "P.aeruginosa_negative", "role": "negative"},
]

_GROUP_ALIASES = {
    "Salmonella enterica": "Salmonella",
    "Escherichia coli": "Escherichia_coli_Shigella",
    "Shigella": "Escherichia_coli_Shigella",
    "Klebsiella pneumoniae": "Klebsiella",
    "Listeria monocytogenes": "Listeria",
    "Campylobacter jejuni": "Campylobacter",
    "Cronobacter sakazakii": "Cronobacter",
}

TRACKED_GROUPS_URL = "https://ftp.ncbi.nlm.nih.gov/pathogen/Results/"
_DIR_HREF_RE = re.compile(r'href="([A-Za-z0-9_.]+)/"')
_NON_PATHOGEN_DIRS = {"BioProject_Hierarchy"}

_GOOD_LEVELS = {"Complete Genome", "Chromosome"}
_GOOD_CATEGORIES = {"reference genome", "representative genome"}


def taxon_to_group(taxon: str) -> str:
    return taxon.replace(" ", "_")


def parse_ftp_listing(html: str) -> list[str]:
    names = _DIR_HREF_RE.findall(html)
    return [n for n in names if n not in _NON_PATHOGEN_DIRS]


def fetch_tracked_groups() -> list[str] | None:
    try:
        request = urllib.request.Request(
            TRACKED_GROUPS_URL, headers={"User-Agent": "hermes-bacmap-validation"}
        )
        with urllib.request.urlopen(request, timeout=30) as resp:
            return parse_ftp_listing(resp.read().decode("utf-8", errors="replace"))
    except OSError:
        return None


def verify_against_tracked_groups(pathogens: list[dict[str, str]], tracked: set[str]) -> list[str]:
    findings = []
    for entry in pathogens:
        candidates = {taxon_to_group(entry["taxon"]), _GROUP_ALIASES.get(entry["taxon"], "")}
        if not candidates & tracked:
            findings.append(f"taxon {entry['taxon']!r} not tracked by NCBI Pathogen Detection")
    return findings


def summary_command(taxon: str) -> list[str]:
    datasets = DATASETS if Path(DATASETS).exists() else shutil.which("datasets") or "datasets"
    return [
        datasets,
        "summary",
        "genome",
        "taxon",
        taxon,
        "--assembly-source",
        "RefSeq",
        "--assembly-level",
        "chromosome,complete",
        "--as-json-lines",
    ]


def _report_dicts(text: str) -> list[dict]:
    stripped = text.strip()
    if not stripped:
        return []
    first = stripped.splitlines()[0]
    if stripped.startswith("{") and '"reports"' in first[:40]:
        try:
            return list(json.loads(stripped).get("reports", []))
        except json.JSONDecodeError:
            return []
    reports = []
    for line in stripped.splitlines():
        try:
            reports.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return reports


def parse_summary(text: str, cap: int = DEFAULT_PER_TAXON) -> list[str]:
    accessions: list[str] = []
    for report in _report_dicts(text):
        info = report.get("assembly_info") or {}
        if info.get("assembly_level") not in _GOOD_LEVELS:
            continue
        if info.get("refseq_category", "na") not in _GOOD_CATEGORIES:
            continue
        accession = report.get("accession")
        if accession and accession not in accessions:
            accessions.append(accession)
        if len(accessions) >= cap:
            break
    return accessions


def _resolve_fna(out_dir: Path, accession: str) -> str:
    genomes = out_dir / "genomes"
    if genomes.is_dir():
        matches = sorted(genomes.glob(f"{accession}*_genomic.fna"))
        if matches:
            return str(matches[0])
    return str(genomes / f"{accession}_genomic.fna")


def write_manifest(out_dir: Path, rows: list[tuple[str, str, str, str]]) -> Path:
    lines = ["accession\torganism\texpected\trole\tfna"]
    for accession, organism, expected, role in rows:
        lines.append(
            f"{accession}\t{organism}\t{expected}\t{role}\t{_resolve_fna(out_dir, accession)}"
        )
    manifest = out_dir / "manifest.tsv"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def _download_accessions(accessions: list[str], out_dir: Path) -> None:
    genomes_dir = out_dir / "genomes"
    genomes_dir.mkdir(parents=True, exist_ok=True)
    acc_list = out_dir / "accessions.txt"
    acc_list.write_text("\n".join(accessions) + "\n")
    zip_path = out_dir / "genomes.zip"
    subprocess.run(
        [
            DATASETS if Path(DATASETS).exists() else "datasets",
            "download",
            "genome",
            "accession",
            "--dehydrated",
            "--include",
            "genome",
            "--inputfile",
            str(acc_list),
            "--filename",
            str(zip_path),
        ],
        check=True,
    )
    subprocess.run(["unzip", "-n", str(zip_path), "-d", str(out_dir)], check=True)
    subprocess.run(
        [
            DATASETS if Path(DATASETS).exists() else "datasets",
            "rehydrate",
            "--directory",
            str(out_dir),
        ],
        check=True,
    )
    for fna in (out_dir / "ncbi_dataset" / "data").glob("**/*_genomic.fna"):
        target = genomes_dir / fna.name
        if not target.exists():
            shutil.copy2(fna, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "tests/fixtures/validation_genomes",
    )
    parser.add_argument("--per-taxon", type=int, default=DEFAULT_PER_TAXON)
    parser.add_argument(
        "--taxa", nargs="*", default=None, help="Subset of taxon names to process (smoke runs)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List planned accessions without downloading"
    )
    parser.add_argument(
        "--verify-list",
        action="store_true",
        help="Check PATHOGENS against the live NCBI tracked-group list and exit",
    )
    args = parser.parse_args(argv)

    if args.verify_list:
        tracked = fetch_tracked_groups()
        if tracked is None:
            print("✗ 无法获取 NCBI 追踪组清单（网络）")
            return 1
        findings = verify_against_tracked_groups(PATHOGENS, set(tracked))
        print(f"live tracked groups: {len(tracked)}")
        for f in findings:
            print(f"LINT: {f}")
        if findings:
            return 1
        print("✓ 所有配置病原均被 NCBI Pathogen Detection 追踪")
        return 0

    selected = [p for p in PATHOGENS if args.taxa is None or p["taxon"] in args.taxa]
    manifest_rows: list[tuple[str, str, str, str]] = []

    for entry in selected:
        result = subprocess.run(summary_command(entry["taxon"]), capture_output=True, text=True)
        accessions = parse_summary(result.stdout, cap=args.per_taxon)
        print(f"{entry['taxon']} [{entry['role']}]: {len(accessions)} genome(s)")
        for accession in accessions:
            manifest_rows.append((accession, entry["taxon"], entry["expected"], entry["role"]))

    if args.dry_run:
        for row in manifest_rows:
            print("  " + "\t".join(row[:4]))
        return 0

    to_download = [
        row[0]
        for row in manifest_rows
        if not (args.out / "genomes" / f"{row[0]}_genomic.fna").exists()
    ]
    if to_download:
        _download_accessions(to_download, args.out)
    else:
        print("all genomes already present")

    manifest = write_manifest(args.out, manifest_rows)
    print(f"manifest (validation truth table): {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
