#!/usr/bin/env python3
"""Snakemake 结果入库：把 summary.json 转为 GenomeObject 存入 SQLite。

用法:
    python scripts/ingest_results.py --sample SAM-TYP-001
    python scripts/ingest_results.py --all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from _common import ROOT

sys.path.insert(0, str(ROOT / "src"))

from hermes_bacmap.services.genome_object_service import (
    GenomeObject,
    GenomeObjectService,
    ObjectType,
)
from hermes_bacmap.services.strain_index import StrainGenotypeIndex, _extract_genotype

RESULTS_DIR = ROOT / "results"
DB_PATH = ROOT / "data" / "hermes_bacmap.sqlite"

PIPELINE_VERSION = "salmonella-workflow-v0.1"
SNP_PIPELINE_VERSION = "snp-pipeline-v0.4"
SCHEMA_VERSION = "0.1.0"

DB_VERSIONS = {
    "abricate_card": "2026-Apr-3",
    "abricate_vfdb": "2026-Apr-3",
    "abricate_plasmidfinder": "2026-Apr-3",
    "gmlst_scheme": "salmonella_2 (PubMLST)",
    "inva_ref": "M90846.1",
}

TOOL_VERSIONS = {
    "fastp": "1.3.5",
    "shovill": "1.1.0",
    "blast": "2.17.0+",
    "gmlst": "0.1.0",
    "sistr": "1.1.3",
    "abricate": "1.4.0",
    "seqkit": "2.8+",
}

SNP_TOOL_VERSIONS = {
    "bwa": "0.7.17",
    "samtools": "1.21",
    "bcftools": "1.21",
    "iqtree": "3.1.2",
}

SNP_DB_VERSIONS = {
    "salmonella": "NC_003197.2 (S. enterica LT2)",
    "ecoli": "NC_000913.3 (E. coli K-12 MG1655)",
    "vpara": "NC_004603.1 + NC_004605.1 (V. parahaemolyticus RIMD 2210633)",
}

SNP_GROUP_ORGANISMS = {
    "salmonella": "Salmonella enterica",
    "ecoli": "Escherichia coli / Shigella",
    "vpara": "Vibrio parahaemolyticus",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_sample(gos: GenomeObjectService, sample_id: str) -> str | None:
    summary_path = RESULTS_DIR / sample_id / "report" / f"{sample_id}_summary.json"
    if not summary_path.exists():
        print(f"  ✗ {sample_id}: summary.json not found")
        return None

    with summary_path.open() as f:
        summary = json.load(f)

    existing = [
        o for o in gos.list_by_type(ObjectType.ANALYSIS)
        if o.strain_id == sample_id
    ]

    if existing:
        latest = max(existing, key=lambda o: o.version)

        if latest.pipeline_version == PIPELINE_VERSION:
            print(f"  ⏭️  {sample_id}: 已存在 v{latest.version} (pipeline={PIPELINE_VERSION}), skipped")
            return latest.object_id

        return _create_new_version(gos, latest.object_id, sample_id, summary, summary_path)

    return _create_new(gos, sample_id, summary, summary_path)


def _build_payload(summary: dict, sample_id: str) -> dict:
    steps = summary.get("steps", {})
    species_verdict = ""
    sp = steps.get("species", {})
    if isinstance(sp, dict):
        species_verdict = sp.get("verdict", "")
    elif isinstance(sp, str):
        species_verdict = sp

    organism = "Salmonella enterica" if "Salmonella" in str(species_verdict) else "Unknown"

    payload = {
        "strain_id": sample_id,
        "species_verdict": species_verdict,
        "qc": steps.get("qc", {}),
        "assembly_stats": steps.get("assembly", ""),
        "mlst": steps.get("mlst", ""),
        "serotype": steps.get("serotype", {}),
        "amr": steps.get("amr", {}),
        "plasmid": steps.get("plasmid", {}),
    }
    return payload, organism


def _register_files(gos: GenomeObjectService, object_id: str, version: int, sample_id: str):
    files_to_register = [
        ("assembly", RESULTS_DIR / sample_id / "assembly" / "contigs.fasta"),
        ("qc_json", RESULTS_DIR / sample_id / "qc" / f"{sample_id}_fastp.json"),
        ("species_blastn", RESULTS_DIR / sample_id / "species" / "invA_blastn.tsv"),
        ("mlst", RESULTS_DIR / sample_id / "typing" / "mlst.tsv"),
        ("sistr", RESULTS_DIR / sample_id / "typing" / "sistr.json"),
        ("amr_card", RESULTS_DIR / sample_id / "amr" / "abricate_card.tsv"),
        ("amr_vfdb", RESULTS_DIR / sample_id / "amr" / "abricate_vfdb.tsv"),
        ("plasmidfinder", RESULTS_DIR / sample_id / "plasmid" / "abricate_plasmidfinder.tsv"),
        ("summary", RESULTS_DIR / sample_id / "report" / f"{sample_id}_summary.json"),
    ]
    for file_type, fpath in files_to_register:
        if fpath.exists() and fpath.stat().st_size > 0:
            gos.register_file_artifact(
                object_id=object_id,
                version=version,
                file_type=file_type,
                file_path=fpath,
                sha256=sha256_file(fpath),
                size_bytes=fpath.stat().st_size,
            )


def _populate_genotype_index(
    index: StrainGenotypeIndex,
    sample_id: str,
    payload: dict,
    organism: str,
    object_id: str,
):
    extracted = _extract_genotype(payload)
    index.upsert(
        strain_id=sample_id,
        organism=organism,
        species=extracted["species"],
        serotype=extracted["serotype"],
        serotype_method=extracted["serotype_method"],
        mlst_scheme=extracted["mlst_scheme"],
        mlst_st=extracted["mlst_st"],
        plasmid_types=extracted["plasmid_types"],
        amr_genes=extracted["amr_genes"],
        object_id=object_id,
        analysis_date=datetime.now(UTC).replace(tzinfo=None).isoformat(),
        pipeline_version=PIPELINE_VERSION,
    )


def _create_new(gos: GenomeObjectService, sample_id: str, summary: dict, summary_path: Path) -> str:
    payload, organism = _build_payload(summary, sample_id)
    object_id = str(uuid4())
    now = datetime.now(UTC).replace(tzinfo=None)

    obj = GenomeObject(
        object_id=object_id,
        object_type=ObjectType.ANALYSIS,
        version=1,
        schema_version=SCHEMA_VERSION,
        created_at=now,
        created_by="salmonella-pipeline",
        payload=payload,
        pipeline_version=PIPELINE_VERSION,
        database_versions=DB_VERSIONS,
        tool_versions=TOOL_VERSIONS,
        organism=organism,
        strain_id=sample_id,
    )
    gos.create(obj)
    _register_files(gos, object_id, 1, sample_id)

    gos.log_event(object_id, "uploaded", {"strain_id": sample_id})
    gos.log_event(object_id, "qc_finished", {"step": "fastp"})
    gos.log_event(object_id, "assembly_finished", {"step": "shovill"})
    gos.log_event(object_id, "amr_finished", {"step": "abricate"})
    gos.log_event(object_id, "report_generated", {"summary_file": str(summary_path)})

    idx = StrainGenotypeIndex(DB_PATH)
    _populate_genotype_index(idx, sample_id, payload, organism, object_id)
    idx.close()

    print(f"  ✅ {sample_id}: 新建 v1 (object_id={object_id[:12]}...)")
    return object_id


def _create_new_version(gos: GenomeObjectService, existing_id: str, sample_id: str, summary: dict, summary_path: Path) -> str:
    payload, organism = _build_payload(summary, sample_id)
    new_obj = gos.create_new_version(
        existing_id,
        payload,
        pipeline_version=PIPELINE_VERSION,
        database_versions=DB_VERSIONS,
        tool_versions=TOOL_VERSIONS,
    )
    _register_files(gos, new_obj.object_id, new_obj.version, sample_id)

    gos.log_event(new_obj.object_id, "version_created", {
        "from_version": new_obj.version - 1,
        "pipeline_version": PIPELINE_VERSION,
    })
    gos.log_event(new_obj.object_id, "report_generated", {"summary_file": str(summary_path)})

    idx = StrainGenotypeIndex(DB_PATH)
    _populate_genotype_index(idx, sample_id, payload, organism, new_obj.object_id)
    idx.close()

    print(f"  🔄 {sample_id}: 新版本 v{new_obj.version} (pipeline={PIPELINE_VERSION})")
    return new_obj.object_id


def ingest_cohort_snp(gos: GenomeObjectService) -> list[str]:
    snp_dir = RESULTS_DIR / "snp"
    if not snp_dir.exists():
        print("  ✗ SNP results directory not found: results/snp/")
        return []

    group_dirs = sorted(
        d for d in snp_dir.iterdir()
        if d.is_dir() and (d / "snp_summary.json").exists()
    )
    if not group_dirs:
        print("  ✗ No per-group SNP summaries found in results/snp/")
        return []

    ingested_ids: list[str] = []
    for group_dir in group_dirs:
        group = group_dir.name
        oid = _ingest_group_snp(gos, group)
        if oid:
            ingested_ids.append(oid)

    return ingested_ids


def _ingest_group_snp(gos: GenomeObjectService, group: str) -> str | None:
    summary_path = RESULTS_DIR / "snp" / group / "snp_summary.json"
    if not summary_path.exists():
        print(f"  ✗ SNP summary not found: {summary_path}")
        return None

    with summary_path.open() as f:
        snp_data = json.load(f)

    cohort_strain_id = f"cohort:{group}-snp"
    existing = [
        o for o in gos.list_by_type(ObjectType.ANALYSIS)
        if o.strain_id == cohort_strain_id
    ]

    if existing:
        latest = max(existing, key=lambda o: o.version)
        if latest.pipeline_version == SNP_PIPELINE_VERSION:
            print(f"  ⏭️  SNP cohort [{group}]: 已存在 v{latest.version}, skipped")
            return latest.object_id
        return _create_cohort_version(gos, latest.object_id, snp_data, group)

    return _create_cohort_new(gos, snp_data, group)


def _build_cohort_payload(snp_data: dict, group: str) -> tuple[dict, str]:
    organism = SNP_GROUP_ORGANISMS.get(group, snp_data.get("organism", group))
    payload = {
        "analysis_type": "snp_cohort",
        "group": group,
        "samples": snp_data.get("samples", []),
        "n_samples": snp_data.get("n_samples", 0),
        "n_snp_sites": snp_data.get("n_snp_sites", 0),
        "missing_rate": snp_data.get("missing_rate", 0),
        "tree_newick": snp_data.get("tree_newick", ""),
        "pairwise_distances": snp_data.get("pairwise_distances", {}),
    }
    return payload, organism


def _register_cohort_files(
    gos: GenomeObjectService, object_id: str, version: int, group: str
):
    group_dir = RESULTS_DIR / "snp" / group
    prefix = f"core_{group}"
    files_to_register = [
        ("snp_tree_newick", group_dir / f"{prefix}.treefile"),
        ("snp_alignment", group_dir / "core_snps.fasta"),
        ("iqtree_report", group_dir / f"{prefix}.iqtree"),
        ("joint_vcf", group_dir / "joint.vcf.gz"),
        ("snp_summary", group_dir / "snp_summary.json"),
    ]
    for file_type, fpath in files_to_register:
        if fpath.exists() and fpath.stat().st_size > 0:
            gos.register_file_artifact(
                object_id=object_id,
                version=version,
                file_type=file_type,
                file_path=fpath,
                sha256=sha256_file(fpath),
                size_bytes=fpath.stat().st_size,
            )


def _link_samples_to_cohort(gos: GenomeObjectService, cohort_object_id: str, samples: list[str]):
    for sid in samples:
        sample_objs = [
            o for o in gos.list_by_type(ObjectType.ANALYSIS)
            if o.strain_id == sid
        ]
        if not sample_objs:
            continue
        latest = max(sample_objs, key=lambda o: o.version)
        try:
            gos.log_event(latest.object_id, "snp_finished", {
                "cohort_object_id": cohort_object_id,
                "strain_id": sid,
            })
        except Exception:
            pass


def _create_cohort_new(
    gos: GenomeObjectService, snp_data: dict, group: str
) -> str:
    payload, organism = _build_cohort_payload(snp_data, group)
    cohort_strain_id = f"cohort:{group}-snp"
    object_id = str(uuid4())
    now = datetime.now(UTC).replace(tzinfo=None)

    obj = GenomeObject(
        object_id=object_id,
        object_type=ObjectType.ANALYSIS,
        version=1,
        schema_version=SCHEMA_VERSION,
        created_at=now,
        created_by="snp-pipeline",
        payload=payload,
        pipeline_version=SNP_PIPELINE_VERSION,
        database_versions={"reference": SNP_DB_VERSIONS.get(group, "unknown")},
        tool_versions=SNP_TOOL_VERSIONS,
        organism=organism,
        strain_id=cohort_strain_id,
    )
    gos.create(obj)
    _register_cohort_files(gos, object_id, 1, group)
    _link_samples_to_cohort(gos, object_id, payload["samples"])

    gos.log_event(object_id, "snp_finished", {
        "group": group,
        "n_samples": payload["n_samples"],
        "n_snp_sites": payload["n_snp_sites"],
    })

    print(
        f"  ✅ SNP cohort [{group}]: 新建 v1 "
        f"({payload['n_samples']} samples, {payload['n_snp_sites']:,} sites)"
    )
    return object_id


def _create_cohort_version(
    gos: GenomeObjectService, existing_id: str, snp_data: dict, group: str
) -> str:
    payload, _ = _build_cohort_payload(snp_data, group)
    new_obj = gos.create_new_version(
        existing_id,
        payload,
        pipeline_version=SNP_PIPELINE_VERSION,
        database_versions={"reference": SNP_DB_VERSIONS.get(group, "unknown")},
        tool_versions=SNP_TOOL_VERSIONS,
    )
    _register_cohort_files(gos, new_obj.object_id, new_obj.version, group)
    _link_samples_to_cohort(gos, new_obj.object_id, payload["samples"])

    gos.log_event(new_obj.object_id, "snp_finished", {
        "group": group,
        "n_samples": payload["n_samples"],
        "n_snp_sites": payload["n_snp_sites"],
    })

    print(f"  🔄 SNP cohort [{group}]: 新版本 v{new_obj.version}")
    return new_obj.object_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Snakemake 结果入库到 GOM")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", type=str)
    group.add_argument("--all", action="store_true")
    group.add_argument("--snp", action="store_true")
    group.add_argument("--rebuild-index", action="store_true")
    args = parser.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    gos = GenomeObjectService(DB_PATH)

    if args.rebuild_index:
        print("=== 重建基因型索引 ===\n")
        idx = StrainGenotypeIndex(DB_PATH)
        gom_conn = sqlite3.connect(str(DB_PATH))
        gom_conn.row_factory = sqlite3.Row
        count = idx.rebuild_from_gom(gom_conn)
        gom_conn.close()
        idx.close()
        print(f"\n✓ 索引重建完成: {count} strains indexed")
        print(f"  Database: {DB_PATH}")
        gos.close()
        return 0

    if args.snp:
        print("=== 入库 SNP Cohort (per-group) ===\n")
        oids = ingest_cohort_snp(gos)
        if oids:
            print(f"\n✓ SNP cohort 入库完成: {len(oids)} group(s)")
            for oid in oids:
                print(f"  object_id={oid[:12]}...")
        else:
            print("\n❌ SNP cohort 入库失败")
        print(f"  Database: {DB_PATH}")
        gos.close()
        return 0 if oids else 1

    if args.all:
        import csv
        samples_tsv = ROOT / "workflows/salmonella/config/samples.tsv"
        with samples_tsv.open() as f:
            samples = [r["sample"] for r in csv.DictReader(f, delimiter="\t")]
    else:
        samples = [args.sample]

    print(f"=== 入库 {len(samples)} 株 ===\n")
    ingested = 0
    for sid in samples:
        oid = ingest_sample(gos, sid)
        if oid:
            print(f"  ✅ {sid}: object_id={oid[:12]}...")
            ingested += 1
        else:
            print(f"  ❌ {sid}: failed")

    print(f"\n✓ 入库完成: {ingested}/{len(samples)}")
    print(f"  Database: {DB_PATH}")

    gos.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
