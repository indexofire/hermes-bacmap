#!/usr/bin/env python3
"""病原菌自动分析编排器（4种病原通用）。

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
import subprocess
import sys

from _common import ROOT
from hermes_bacmap.services.sample_summary import (
    classify_samples,
    read_summary,
    summary_fields,
    summary_path,
)

PIXI_BIN = ROOT / ".pixi/envs/default/bin"
WORKFLOW_DIR = ROOT / "workflows/bacmap"
RESULTS_DIR = ROOT / "results"


def validate_sample(sample: str) -> None:
    import csv

    samples_tsv = WORKFLOW_DIR / "config/samples.tsv"
    if not samples_tsv.exists():
        print(f"❌ samples.tsv not found: {samples_tsv}")
        sys.exit(1)
    with samples_tsv.open() as f:
        valid = {r["sample"] for r in csv.DictReader(f, delimiter="\t")}
    if sample not in valid:
        print(f"❌ Unknown sample: {sample}")
        print(f"   Valid samples: {', '.join(sorted(valid))}")
        sys.exit(1)


def run_snakemake(targets: list[str], cores: int = 8, timeout: int = 7200) -> bool:
    import os

    env = dict(os.environ)
    env["PATH"] = f"{PIXI_BIN}:{env['PATH']}"

    cmd = [
        str(PIXI_BIN / "snakemake"),
        "-s",
        str(WORKFLOW_DIR / "Snakefile"),
        "--cores",
        str(cores),
        "--rerun-incomplete",
        "--printshellcmds",
    ] + targets

    print(f"\n{'=' * 60}")
    print(f"启动 Snakemake 自动编排 ({len(targets)} target(s))")
    print(f"Cores: {cores}")
    print(f"{'=' * 60}\n")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(WORKFLOW_DIR),
            env=env,
            timeout=timeout,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"\n❌ Snakemake 超时 ({timeout}s)。可能卡在锁等待或资源争用。")
        print(f"   检查: snakemake --unlock (在 {WORKFLOW_DIR} 下)")
        return False


def check_status(sample: str | None = None) -> dict:
    import csv

    samples_tsv = WORKFLOW_DIR / "config/samples.tsv"
    with samples_tsv.open() as f:
        all_samples = [r["sample"] for r in csv.DictReader(f, delimiter="\t")]

    ids = [s for s in all_samples if not sample or s == sample]
    return classify_samples(RESULTS_DIR, ids)


def interpret_summary(sample: str) -> None:
    summary = read_summary(RESULTS_DIR, sample)
    if summary is None:
        print(f"  ❌ {sample}: summary not found")
        return

    print(f"\n{'=' * 60}")
    print(f"  {sample} 分析结果")
    print(f"{'=' * 60}")

    fields = summary_fields(summary)

    verdict = fields["species"]
    icon = "✅" if verdict != "N/A" and verdict != "Unknown" else "❌"
    print(f"\n  {icon} Species: {verdict}")

    if fields["mlst_st"] != "N/A":
        print(f"  🧬 MLST: ST{fields['mlst_st']}")

    serotype = summary.get("steps", {}).get("serotype", {})
    if isinstance(serotype, dict):
        print(f"  🔬 Serotype (SISTR): {fields['serotype']}")

    amr = summary.get("steps", {}).get("amr", {})
    if isinstance(amr, dict):
        amrfp = amr.get("amrfinderplus", [])
        if amrfp:
            genes = [r.get("Gene symbol", "?") for r in amrfp if isinstance(r, dict)]
            print(f"  💊 AMR genes ({len(genes)}): {', '.join(genes[:10])}")
        else:
            print("  💊 AMR genes: none found (susceptible)")

    print(f"\n  Full report: {summary_path(RESULTS_DIR, sample)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="病原菌自动分析编排器（4种病原通用）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", type=str, help="Sample ID to analyze")
    group.add_argument("--all", action="store_true", help="Analyze all samples")
    group.add_argument("--snp", action="store_true", help="Run SNP cohort analysis")
    group.add_argument("--status", action="store_true", help="Check analysis status")
    parser.add_argument("--cores", type=int, default=8)
    args = parser.parse_args()

    if args.status:
        status = check_status(None)

        print(f"\n{'=' * 60}")
        print("  分析状态")
        print(f"{'=' * 60}")

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

        snp = status.get("snp_cohort", {})
        snp_icon = "✅" if snp.get("summary") else ("🔄" if snp.get("tree") else "⬜")
        print(
            f"\n  {snp_icon} SNP Cohort: tree={'yes' if snp.get('tree') else 'no'}, "
            f"summary={'yes' if snp.get('summary') else 'no'}"
        )

        print()
        return 0

    if args.snp:
        target = str(ROOT / "results" / "snp" / "snp_summary.json")
        targets = [target]
    elif args.sample:
        validate_sample(args.sample)
        target = str(ROOT / "results" / args.sample / "report" / f"{args.sample}_summary.json")
        targets = [target]
    elif args.all:
        targets = []
    else:
        return 1

    success = run_snakemake(targets, args.cores)

    if success:
        if args.snp:
            print("\n✅ SNP cohort analysis 完成。")
            print(f"   Tree: {RESULTS_DIR / 'snp' / 'core.treefile'}")
            print(f"   Summary: {RESULTS_DIR / 'snp' / 'snp_summary.json'}")
            print("   Report: python scripts/generate_report.py --cohort")
            print("   Ingest: python scripts/ingest_results.py --snp")
        elif args.sample:
            interpret_summary(args.sample)
        else:
            import csv

            failed = []
            with (WORKFLOW_DIR / "config/samples.tsv").open() as f:
                for r in csv.DictReader(f, delimiter="\t"):
                    sid = r["sample"]
                    summary = RESULTS_DIR / sid / "report" / f"{sid}_summary.json"
                    if summary.exists():
                        interpret_summary(sid)
                    else:
                        failed.append(sid)
                        print(f"  ❌ {sid}: summary not found")
            if failed:
                print(f"\n⚠️  {len(failed)} sample(s) failed: {', '.join(failed)}")
                print(f"\n✅ 部分完成 ({len(failed)} 失败)。")
                return 1
        print("\n✅ 全部完成。")
        return 0
    else:
        import sys as _sys

        _sys.path.insert(0, str(ROOT / "src"))
        from hermes_bacmap.analysis.failure_diagnostics import diagnose_from_log

        diag = diagnose_from_log(str(WORKFLOW_DIR / ".snakemake/log"))

        print("\n❌ Snakemake 失败。诊断结果:")
        print(f"   类型: {diag.error_type}")
        print(f"   原因: {diag.details}")
        if diag.rule_name:
            print(f"   规则: {diag.rule_name}")
        print(f"   修复: {diag.suggested_fix}")
        if diag.recovery_commands:
            print("   命令:")
            for cmd in diag.recovery_commands:
                print(f"     $ {cmd}")
        print(f"\n   手动检查: {WORKFLOW_DIR}/.snakemake/log/")
        return 1


if __name__ == "__main__":
    sys.exit(main())
