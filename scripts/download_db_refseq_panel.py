#!/usr/bin/env python3
"""Build the curated RefSeq ANI panel (species-id A-mini).

Candidates come from the live NCBI Pathogen Detection tracked-group list
(https://ftp.ncbi.nlm.nih.gov/pathogen/Results/). Genome metadata is taken
from a single assembly_summary_refseq.txt download and filtered locally
(much faster than per-taxon datasets queries). Selection rule:

  - refseq_category == "reference genome"  -> ALL included (mandatory)
  - assembly_level == "Complete Genome"    -> up to --max-complete more
    (representative first); everything else skipped

Output: data/db/refseq_panel/{genomes/*.fna, panel.sketch, metadata.tsv}
plus a manifest consumed by ani_identifier for the evidence chain.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

DATASETS = str(ROOT / ".pixi/envs/default/bin/datasets")
SKANI = str(ROOT / ".pixi/envs/default/bin/skani")
ASSEMBLY_SUMMARY_URL = "https://ftp.ncbi.nlm.nih.gov/genomes/refseq/assembly_summary_refseq.txt"

QUERY_ALIASES = {
    "Escherichia_coli_Shigella": ["Escherichia coli", "Shigella"],
}
FUNGI_GROUPS = {"Candidozyma_auris"}


def _datasets_bin() -> str:
    return DATASETS if Path(DATASETS).exists() else shutil.which("datasets") or "datasets"


def group_to_queries(group: str) -> list[str]:
    if group in QUERY_ALIASES:
        return list(QUERY_ALIASES[group])
    return [group.replace("_", " ")]


def bacterial_groups(groups: list[str]) -> list[str]:
    return [g for g in groups if g not in FUNGI_GROUPS]


def _candidate_prefixes(groups: list[str]) -> list[str]:
    prefixes: list[str] = []
    for group in groups:
        prefixes.extend(group_to_queries(group))
    return sorted(set(prefixes))


def parse_summary_rows(text: str) -> list[dict]:
    rows = []
    for line in text.strip().splitlines():
        try:
            report = json.loads(line)
        except json.JSONDecodeError:
            continue
        info = report.get("assembly_info") or {}
        rows.append(
            {
                "accession": report.get("accession", ""),
                "organism": (report.get("organism") or {}).get("organism_name", ""),
                "level": info.get("assembly_level", ""),
                "category": info.get("refseq_category", "na"),
            }
        )
    return rows


def select_panel_rows(rows: list[dict], max_complete: int = 5) -> list[dict]:
    """Per species (species_taxid): all reference genomes, plus up to
    max_complete Complete-Genome assemblies (representative first)."""
    by_species: dict[str, list[dict]] = {}
    for row in rows:
        by_species.setdefault(row.get("species_taxid", ""), []).append(row)

    selected: dict[str, dict] = {}
    for _, members in sorted(by_species.items()):
        refs = [m for m in members if m["category"] == "reference genome"]
        ref_ids = {m["accession"] for m in refs}
        completes = [
            m for m in members if m["level"] == "Complete Genome" and m["accession"] not in ref_ids
        ]
        completes.sort(key=lambda m: (m["category"] != "representative genome",))
        for row in refs + completes[:max_complete]:
            selected[row["accession"]] = row
    return [selected[a] for a in sorted(selected)]


def load_summary_rows(summary_path: Path, prefixes: list[str]) -> list[dict]:
    rows = []
    with summary_path.open() as fh:
        header = None
        body = []
        for ln in fh:
            if ln.startswith("#"):
                if "assembly_accession" in ln:
                    header = ln.lstrip("# ").rstrip("\n").split("\t")
                continue
            if header:
                body.append(ln)
        for rec in csv.DictReader(body, fieldnames=header, delimiter="\t"):
            organism = rec.get("organism_name", "")
            if not organism.startswith(tuple(prefixes)):
                continue
            rows.append(
                {
                    "accession": rec.get("assembly_accession", ""),
                    "organism": organism,
                    "level": rec.get("assembly_level", ""),
                    "category": rec.get("refseq_category", "na"),
                    "taxid": rec.get("taxid", ""),
                    "species_taxid": rec.get("species_taxid", ""),
                }
            )
    return rows


def build_group_records(
    groups: list[str], candidate_rows: list[dict], selected_rows: list[dict]
) -> list[tuple[str, str, int, int, int]]:
    """(group, taxids;joined, n_reference, n_complete, n_total) per group.

    Attribution: each selected row belongs to the group whose query prefix
    is the longest match on organism_name.
    """
    prefix_to_group: dict[str, str] = {}
    for group in groups:
        for query in group_to_queries(group):
            cur = prefix_to_group.get(query)
            if cur is None or len(group) > len(cur):
                prefix_to_group[query] = group
    queries = sorted(prefix_to_group, key=len, reverse=True)

    def _group_of(organism: str) -> str:
        for query in queries:
            if organism.startswith(query):
                return prefix_to_group[query]
        return ""

    stats: dict[str, dict] = {}
    for row in selected_rows:
        group = _group_of(row["organism"])
        if not group:
            continue
        st = stats.setdefault(group, {"taxids": set(), "ref": 0, "comp": 0, "total": 0})
        st["taxids"].add(row.get("species_taxid", ""))
        st["total"] += 1
        if row["category"] == "reference genome":
            st["ref"] += 1
        elif row["level"] == "Complete Genome":
            st["comp"] += 1

    return [
        (
            group,
            ";".join(sorted(t for t in stats.get(group, {}).get("taxids", set()) if t)),
            stats.get(group, {}).get("ref", 0),
            stats.get(group, {}).get("comp", 0),
            stats.get(group, {}).get("total", 0),
        )
        for group in sorted(groups)
    ]


def write_panel_manifest(panel_dir: Path, n_genomes: int) -> Path:
    blob = (panel_dir / "metadata.tsv").read_bytes() + f"\n{n_genomes}".encode()
    checksum = hashlib.sha256(blob).hexdigest()
    manifests = panel_dir.parent / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    manifest = manifests / "refseq_panel.json"
    manifest.write_text(
        json.dumps(
            {
                "name": "refseq_panel",
                "downloaded_at": datetime.now(UTC).isoformat(),
                "source": "NCBI Pathogen Detection tracked groups + RefSeq",
                "checksum": checksum,
                "n_genomes": n_genomes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


def emit_panel_records(
    panel_dir: Path, candidates: list[str], candidate_rows: list[dict], selected: list[dict]
) -> tuple[Path, Path, Path]:
    tracked_tsv = panel_dir / "tracked_pathogens.tsv"
    with tracked_tsv.open("w", encoding="utf-8") as fh:
        fh.write("group\ttaxids\tn_reference\tn_complete\tn_total\n")
        for group, taxids, n_ref, n_comp, n_total in build_group_records(
            candidates, candidate_rows, selected
        ):
            fh.write(f"{group}\t{taxids}\t{n_ref}\t{n_comp}\t{n_total}\n")

    acc_tsv = panel_dir / "panel_accessions.tsv"
    with acc_tsv.open("w", encoding="utf-8") as fh:
        fh.write("accession\torganism\ttaxid\tspecies_taxid\tcategory\tlevel\n")
        for row in selected:
            fh.write(
                f"{row['accession']}\t{row['organism']}\t{row.get('taxid', '')}"
                f"\t{row.get('species_taxid', '')}\t{row['category']}\t{row['level']}\n"
            )

    records = build_group_records(candidates, candidate_rows, selected)
    n_ref = sum(r[2] for r in records)
    n_comp = sum(r[3] for r in records)
    md = ROOT / "docs" / "reference" / "pathogen-panel.md"
    lines = [
        "# 病原面板数据库台账（refseq_panel）",
        "",
        "候选病原：NCBI Pathogen Detection 追踪组",
        "（ftp.ncbi.nlm.nih.gov/pathogen/Results，构建时活清单对账）。",
        "选择规则：每物种（species_taxid）reference 必选 + complete ≤5（representative 优先），",
        f"共 **{len(selected)} 株**（reference {n_ref} + complete {n_comp}）。",
        "",
        "机器可读台账（本地，随库分发）：`data/db/refseq_panel/tracked_pathogens.tsv`、"
        "`panel_accessions.tsv`（全量 accession）；skani 库 `panel.sketch`。",
        "",
        "| 追踪组 | species taxid | reference | complete | 合计 |",
        "|---|---|---|---|---|",
    ]
    for group, taxids, r, c, total in records:
        taxid_cell = taxids or "—"
        n_taxids = len(taxids.split(";")) if taxids else 0
        if n_taxids > 10:
            taxid_cell = f"{n_taxids} 个物种 taxid（全表见 TSV）"
        lines.append(f"| {group} | {taxid_cell} | {r} | {c} | {total} |")
    lines.append("")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tracked_tsv, acc_tsv, md


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/db")
    parser.add_argument("--max-complete", type=int, default=5)
    parser.add_argument(
        "--groups",
        nargs="*",
        default=None,
        help="Restrict to these FTP group names (default: all tracked bacteria)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--records-only",
        action="store_true",
        help="Re-emit tracked-pathogen/accession records from local data only",
    )
    args = parser.parse_args(argv)

    from download_validation_genomes import fetch_tracked_groups

    tracked = fetch_tracked_groups()
    if tracked is None:
        print("✗ 无法获取 FTP 追踪清单（网络）")
        return 1
    candidates = bacterial_groups(args.groups) if args.groups else bacterial_groups(tracked)
    print(f"候选病原组: {len(candidates)}（追踪组共 {len(tracked)}）")

    panel = args.data_root / "refseq_panel"
    genomes_dir = panel / "genomes"
    genomes_dir.mkdir(parents=True, exist_ok=True)

    summary_path = panel / "assembly_summary_refseq.txt"
    if not summary_path.exists():
        print("下载 assembly_summary_refseq.txt (~229MB, 断点续传)...")
        wget = shutil.which("wget")
        if wget:
            subprocess.run(
                [wget, "-c", "-q", "-O", str(summary_path), ASSEMBLY_SUMMARY_URL],
                check=True,
            )
        else:
            curl = shutil.which("curl") or "curl"
            subprocess.run(
                [curl, "-sSfL", "-C", "-", "-o", str(summary_path), ASSEMBLY_SUMMARY_URL],
                check=True,
            )

    prefixes = _candidate_prefixes(candidates)
    candidate_rows = load_summary_rows(summary_path, prefixes)
    organisms = sorted({r["organism"] for r in candidate_rows})
    print(f"涉及物种 {len(organisms)}，候选装配行 {len(candidate_rows)}")

    selected = select_panel_rows(candidate_rows, max_complete=args.max_complete)
    n_ref = sum(1 for r in selected if r["category"] == "reference genome")
    print(
        f"选中 {len(selected)}（reference {n_ref} 必选 + "
        f"complete {len(selected) - n_ref} ≤{args.max_complete}）"
    )

    if args.records_only:
        accessions = set((panel / "accessions.txt").read_text().split())
        selected = [r for r in candidate_rows if r["accession"] in accessions]
        tracked_tsv, acc_tsv, md = emit_panel_records(panel, candidates, candidate_rows, selected)
        print(f"✓ 台账: {tracked_tsv} / {acc_tsv} / {md}")
        return 0

    if args.dry_run:
        for row in selected[:20]:
            print(f"  {row['accession']}\t{row['category']}\t{row['organism']}")
        return 0

    accessions = sorted(r["accession"] for r in selected)
    acc_list = panel / "accessions.txt"
    acc_list.write_text("\n".join(accessions) + "\n")
    zip_path = panel / "genomes.zip"
    datasets = _datasets_bin()
    subprocess.run(
        [
            datasets,
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
    subprocess.run(["unzip", "-n", str(zip_path), "-d", str(panel)], check=True)
    subprocess.run([datasets, "rehydrate", "--directory", str(panel)], check=True)

    for fna in (panel / "ncbi_dataset" / "data").glob("**/*_genomic.fna"):
        target = genomes_dir / fna.name
        if not target.exists():
            shutil.copy2(fna, target)

    org_by_acc = {r["accession"]: r["organism"] for r in selected}
    n = 0
    with (panel / "metadata.tsv").open("w", encoding="utf-8") as fh:
        fh.write("fna\tspecies\n")
        for fna in sorted(genomes_dir.glob("*_genomic.fna")):
            acc = fna.name.split("_ASM")[0]
            fh.write(f"{fna.name}\t{org_by_acc.get(acc, acc)}\n")
            n += 1

    fnas = sorted(str(f) for f in genomes_dir.glob("*_genomic.fna"))
    subprocess.run(
        [
            SKANI if Path(SKANI).exists() else "skani",
            "sketch",
            *fnas,
            "-o",
            str(panel / "panel.sketch"),
        ],
        check=True,
    )
    manifest = write_panel_manifest(panel, n_genomes=n)
    tracked_tsv, acc_tsv, md = emit_panel_records(panel, candidates, candidate_rows, selected)
    print(f"✓ panel: {n} genomes → {panel / 'panel.sketch'}")
    print(f"✓ manifest: {manifest}")
    print(f"✓ 台账: {tracked_tsv.name}, {acc_tsv.name}, {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
