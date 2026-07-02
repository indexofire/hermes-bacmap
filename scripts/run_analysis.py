#!/usr/bin/env python3
"""Salmonella 自动分析编排器。

一次命令自动完成：QC → 组装 → 物种验证 → MLST → 血清型 → AMR → 毒力 → 报告。
Snakemake DAG 自动编排所有依赖，无需人为逐步触发。

用法:
    python scripts/run_analysis.py --sample SAM-TYP-001
    python scripts/run_analysis.py --all
    python scripts/run_analysis.py --status
    python scripts/run_analysis.py --status --sample SAM-TYP-001
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _common import ROOT
PIXI_BIN = ROOT / ".pixi/envs/default/bin"
WORKFLOW_DIR = ROOT / "workflows/salmonella"
RESULTS_DIR = ROOT / "results"


def run_snakemake(targets: list[str], cores: int = 8) -> bool:
    env = {"PATH": f"{PIXI_BIN}:{__import__('os').environ['PATH']}"}
    cmd = [
        str(PIXI_BIN / "snakemake"),
        "-s", str(WORKFLOW_DIR / "Snakefile"),
        "--cores", str(cores),
        "--rerun-incomplete",
        "--printshellcmds",
    ] + targets

    print(f"\n{'='*60}")
    print(f"启动 Snakemake 自动编排 ({len(targets)} target(s))")
    print(f"Cores: {cores}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=str(WORKFLOW_DIR), env=env)
    return result.returncode == 0


def check_status(sample: str | None = None) -> dict:
    samples_done = {}
    samples_in_progress = {}
    samples_not_started = []

    import csv
    samples_tsv = WORKFLOW_DIR / "config/samples.tsv"
    with samples_tsv.open() as f:
        all_samples = [r["sample"] for r in csv.DictReader(f, delimiter="\t")]

    targets = [sample] if sample else all_samples

    for s in all_samples:
        if sample and s != sample:
            continue

        summary = RESULTS_DIR / s / "report" / f"{s}_summary.json"
        contigs = RESULTS_DIR / s / "assembly" / "contigs.fasta"
        qc_json = RESULTS_DIR / s / "qc" / f"{s}_fastp.json"
        species = RESULTS_DIR / s / "species" / "species_verdict.txt"
        mlst = RESULTS_DIR / s / "typing" / "mlst.tsv"
        amr = RESULTS_DIR / s / "amr" / "amrfinderplus.tsv"
        report = RESULTS_DIR / s / "report" / f"{s}_summary.json"

        steps = {
            "qc": qc_json.exists(),
            "assembly": contigs.exists(),
            "species": species.exists(),
            "mlst": mlst.exists(),
            "amr": amr.exists(),
            "report": report.exists(),
        }
        done_count = sum(steps.values())

        if report.exists():
            samples_done[s] = steps
        elif done_count > 0:
            samples_in_progress[s] = steps
        else:
            samples_not_started.append(s)

    return {
        "done": samples_done,
        "in_progress": samples_in_progress,
        "not_started": samples_not_started,
    }


def interpret_summary(sample: str) -> None:
    summary_path = RESULTS_DIR / sample / "report" / f"{sample}_summary.json"
    if not summary_path.exists():
        print(f"  ❌ {sample}: summary not found")
        return

    with summary_path.open() as f:
        summary = json.load(f)

    print(f"\n{'='*60}")
    print(f"  {sample} 分析结果")
    print(f"{'='*60}")

    species = summary.get("steps", {}).get("species", {})
    verdict = species.get("species", "N/A") if isinstance(species, dict) else str(species)
    icon = "✅" if verdict != "N/A" and verdict != "Unknown" else "❌"
    print(f"\n  {icon} Species: {verdict}")

    mlst_raw = summary.get("steps", {}).get("mlst", "")
    if mlst_raw and mlst_raw != "N/A":
        parts = mlst_raw.strip().split("\t")
        if len(parts) >= 2:
            print(f"  🧬 MLST: {parts[-1]}")

    serotype = summary.get("steps", {}).get("serotype", {})
    if isinstance(serotype, dict):
        sistr = serotype.get("sistr", "N/A")
        print(f"  🔬 Serotype (SISTR): {sistr}")

    amr = summary.get("steps", {}).get("amr", {})
    if isinstance(amr, dict):
        amrfp = amr.get("amrfinderplus", [])
        if amrfp:
            genes = [r.get("Gene symbol", "?") for r in amrfp if isinstance(r, dict)]
            print(f"  💊 AMR genes ({len(genes)}): {', '.join(genes[:10])}")
        else:
            print(f"  💊 AMR genes: none found (susceptible)")

    print(f"\n  Full report: {summary_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Salmonella 自动分析编排器")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", type=str, help="Sample ID to analyze")
    group.add_argument("--all", action="store_true", help="Analyze all samples")
    group.add_argument("--status", action="store_true", help="Check analysis status")
    parser.add_argument("--cores", type=int, default=8)
    args = parser.parse_args()

    if args.status:
        sample = None
        status = check_status(sample)

        print(f"\n{'='*60}")
        print("  分析状态")
        print(f"{'='*60}")

        if status["done"]:
            print(f"\n  ✅ 完成 ({len(status['done'])} 株):")
            for s, steps in status["done"].items():
                print(f"     {s}")
        if status["in_progress"]:
            print(f"\n  🔄 进行中 ({len(status['in_progress'])} 株):")
            for s, steps in status["in_progress"].items():
                done = sum(steps.values())
                total = len(steps)
                details = ", ".join(k for k, v in steps.items() if v)
                print(f"     {s}: {done}/{total} steps ({details})")
        if status["not_started"]:
            print(f"\n  ⬜ 未开始 ({len(status['not_started'])} 株):")
            for s in status["not_started"]:
                print(f"     {s}")

        print()
        return 0

    if args.sample:
        sample = args.sample
    elif args.all:
        import csv
        with (WORKFLOW_DIR / "config/samples.tsv").open() as f:
            all_samples = [r["sample"] for r in csv.DictReader(f, delimiter="\t")]
        sample = None
    else:
        return 1

    if sample:
        target = str(ROOT / "results" / sample / "report" / f"{sample}_summary.json")
        targets = [target]
    else:
        targets = []

    success = run_snakemake(targets, args.cores)

    if success:
        if sample:
            interpret_summary(sample)
        else:
            import csv
            with (WORKFLOW_DIR / "config/samples.tsv").open() as f:
                for r in csv.DictReader(f, delimiter="\t"):
                    interpret_summary(r["sample"])
        print(f"\n✅ 全部完成。")
        return 0
    else:
        print(f"\n❌ Snakemake 失败。检查 .snakemake/log/ 了解详情。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
