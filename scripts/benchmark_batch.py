"""96 株 batch 基准（project.md §2.2 验收：96 株 ≤8h，V0.7 Wave 4）。

三级子命令：
  prepare     从现有 gold standard FASTQ 下采样合成 N 个基准样本
              （seqkit sample --two-pass，同 seed 保配对），
              写 workflows/bacmap/config/samples_bench.tsv
  run         独立 workdir（results-bench/）跑 Snakemake，记录墙钟时间
              → results-bench/bench_timing.json
  extrapolate 读计时 JSON，按 株数 × 读段数 线性外推 96 株规模，
              渲染 docs/benchmark-report.md

用法：
    python scripts/benchmark_batch.py prepare --n-strains 4 --reads 150000
    python scripts/benchmark_batch.py run --cores 15
    python scripts/benchmark_batch.py extrapolate --target-strains 96 --target-reads 1000000
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

from _common import ROOT, validate_sample_name  # noqa: E402

PIXI_BIN = ROOT / ".pixi/envs/default/bin"
WORKFLOW_DIR = ROOT / "workflows/bacmap"
GOLD_DATA = ROOT / "tests/fixtures/gold_standard/salmonella/data"
BENCH_DATA = ROOT / "data/benchmark"
BENCH_SAMPLES_TSV = WORKFLOW_DIR / "config/samples_bench.tsv"
BENCH_WORKDIR = "results-bench"
BENCH_RESULTS = ROOT / "results-bench"
TIMING_JSON = BENCH_RESULTS / "bench_timing.json"
TARGET_HOURS = 8.0


@dataclass(frozen=True)
class Extrapolation:
    target_seconds: float
    target_hours: float
    meets_8h_target: bool


def extrapolate(
    measured_seconds: float,
    bench_strains: int,
    bench_reads_per_strain: int,
    target_strains: int,
    target_reads_per_strain: int,
) -> Extrapolation:
    """线性外推：每株每读段成本恒定（SPAdes 近线性于读深，浅段略保守）。"""
    per_strain_per_read = measured_seconds / bench_strains / bench_reads_per_strain
    target_seconds = per_strain_per_read * target_strains * target_reads_per_strain
    return Extrapolation(
        target_seconds=target_seconds,
        target_hours=target_seconds / 3600.0,
        meets_8h_target=target_seconds / 3600.0 <= TARGET_HOURS,
    )


def render_samples_tsv(rows: list[tuple[str, str, str, str]]) -> str:
    out = ["sample\tspecies\tR1\tR2"]
    out += [f"{s}\t{sp}\t{r1}\t{r2}" for s, sp, r1, r2 in rows]
    return "\n".join(out) + "\n"


def cmd_prepare(args: argparse.Namespace) -> int:
    seqkit = PIXI_BIN / "seqkit"
    sources = sorted(p for p in GOLD_DATA.iterdir() if p.is_dir())
    if not sources:
        print("no gold standard FASTQ dirs found", file=sys.stderr)
        return 1
    picked = sources[: args.n_strains]
    # P2-3：请求株数不足时显式告警（静默缩量会让外推口径失真）
    if len(picked) < args.n_strains:
        print(
            f"⚠ only {len(picked)} source strains available "
            f"(requested {args.n_strains}); extrapolation must use {len(picked)}",
            file=sys.stderr,
        )

    rows: list[tuple[str, str, str, str]] = []
    for i, src in enumerate(picked, 1):
        bench_id = f"BEN-{i:03d}"
        dst = BENCH_DATA / bench_id
        dst.mkdir(parents=True, exist_ok=True)
        for mate in ("R1", "R2"):
            src_fq = next(iter(src.glob(f"*_{mate}.fastq.gz")), None)
            if src_fq is None:
                print(f"missing {mate} FASTQ for {src.name}", file=sys.stderr)
                return 1
            out_fq = dst / f"{bench_id}_{mate}.fastq.gz"
            cmd = [
                str(seqkit),
                "sample",
                "-n",
                str(args.reads),
                "-s",
                str(args.seed),
                "--two-pass",
                str(src_fq),
                "-o",
                str(out_fq),
            ]
            # -o 显式输出（按扩展名写 gzip）；stdout 重定向会是明文
            proc = subprocess.run(cmd, check=False)  # noqa: S603
            if proc.returncode != 0:
                print(f"seqkit failed for {src_fq}", file=sys.stderr)
                return 1
            print(f"  {bench_id}_{mate}.fastq.gz  ({args.reads} reads)")
        r1_rel = str((dst / f"{bench_id}_R1.fastq.gz").relative_to(ROOT))
        r2_rel = str((dst / f"{bench_id}_R2.fastq.gz").relative_to(ROOT))
        rows.append((bench_id, "Salmonella", r1_rel, r2_rel))

    BENCH_SAMPLES_TSV.write_text(render_samples_tsv(rows))
    print(f"samples_bench.tsv: {len(rows)} strains → {BENCH_SAMPLES_TSV}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    import os

    if not BENCH_SAMPLES_TSV.exists():
        print("run 'prepare' first", file=sys.stderr)
        return 1
    with BENCH_SAMPLES_TSV.open() as f:
        samples = [r["sample"] for r in csv.DictReader(f, delimiter="\t")]
    # P2-3（安全，沿袭 1a7026e 决策）：bench 样本名经 snakemake 插值进 shell，
    # 必须过白名单（samples_bench.tsv 若被手编，此处兜底）
    try:
        for s in samples:
            validate_sample_name(s)
    except ValueError as e:
        print(f"unsafe sample name in samples_bench.tsv: {e}", file=sys.stderr)
        return 1

    env = dict(os.environ)
    env["PATH"] = f"{PIXI_BIN}:{env['PATH']}"
    # 规则输出是绝对路径（WORKDIR 解析后拼接），相对 target 匹配不上
    targets = [str(BENCH_RESULTS / s / "report" / f"{s}_summary.json") for s in samples]
    cmd = [
        str(PIXI_BIN / "snakemake"),
        "-s",
        str(WORKFLOW_DIR / "Snakefile"),
        "--cores",
        str(args.cores),
        "--rerun-incomplete",
        *targets,
        # --config 为 nargs+，会吞掉后续非 flag 参数——targets 必须放在前面
        "--config",
        f"samples_file={BENCH_SAMPLES_TSV.relative_to(WORKFLOW_DIR)}",
        f"workdir={BENCH_WORKDIR}",
    ]
    print(f"benchmark: {len(samples)} strains × {args.reads_hint} reads, cores={args.cores}")
    t0 = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(WORKFLOW_DIR), env=env, check=False)  # noqa: S603
    elapsed = time.monotonic() - t0
    BENCH_RESULTS.mkdir(parents=True, exist_ok=True)
    TIMING_JSON.write_text(
        json.dumps(
            {
                "bench_strains": len(samples),
                "reads_per_strain": args.reads_hint,
                "cores": args.cores,
                "measured_seconds": round(elapsed, 1),
                "snakemake_returncode": proc.returncode,
                # P2-5：计时口径出处（单次全量实测；外推报告引用此字段）
                "timing_source": "single_full_run_wall_clock",
            },
            indent=2,
        )
    )
    print(f"wall time: {elapsed:.1f}s → {TIMING_JSON}")
    return proc.returncode


def render_benchmark_md(
    bench_strains: int,
    bench_reads: int,
    cores: int,
    measured_seconds: float,
    estimate: Extrapolation,
    target_strains: int,
    target_reads: int,
    timing_source: str = "single_full_run_wall_clock",
) -> str:
    verdict = "✅ 满足" if estimate.meets_8h_target else "❌ 不满足"
    return "\n".join(
        [
            "# 96-Strain Batch Benchmark",
            "",
            "> 生成：`python scripts/benchmark_batch.py`（V0.7 Wave 4）。",
            "> 线性外推模型：每株每读段成本恒定；§2.2 的 ≤8h 目标按推荐档（24c/48t）设定，",
            "> 本机结果需按核数另行折算。",
            "",
            "## Benchmark setup",
            "",
            f"- bench strains: **{bench_strains}** × {bench_reads:,} read pairs"
            f"（seqkit 下采样自 gold standard）",
            f"- cores: **{cores}**（计时机；跨机复跑请以 bench_timing.json 为准）",
            f"- measured wall time: **{measured_seconds:.1f}s**（{measured_seconds / 3600:.2f}h）",
            f"- timing source: `{timing_source}`",
            "",
            "## Extrapolation to 96 strains",
            "",
            f"- {target_strains:,} 株 × {target_reads:,} read pairs @ {cores} cores："
            f"**{estimate.target_seconds:.0f}s ≈ {estimate.target_hours:.1f}h**",
            f"- vs 目标 ≤8h（推荐档 24c/48t）：{verdict}",
            "",
            "## Notes",
            "",
            "- SPAdes 装配是核心瓶颈（project.md §7.4）；浅深度下采样对外推偏乐观，",
            "  全读深单株耗时更高，结论以全量跑为准。",
            "- 基准跑批完全隔离：`samples_bench.tsv` + `results-bench/`，不触碰生产 results/。",
            "",
        ]
    )


def cmd_extrapolate(args: argparse.Namespace) -> int:
    if not TIMING_JSON.exists():
        print("run 'run' first", file=sys.stderr)
        return 1
    timing = json.loads(TIMING_JSON.read_text())
    est = extrapolate(
        measured_seconds=timing["measured_seconds"],
        bench_strains=timing["bench_strains"],
        bench_reads_per_strain=timing["reads_per_strain"],
        target_strains=args.target_strains,
        target_reads_per_strain=args.target_reads,
    )
    md = render_benchmark_md(
        bench_strains=timing["bench_strains"],
        bench_reads=timing["reads_per_strain"],
        cores=timing["cores"],
        measured_seconds=timing["measured_seconds"],
        estimate=est,
        target_strains=args.target_strains,
        target_reads=args.target_reads,
        timing_source=str(timing.get("timing_source", "unspecified")),
    )
    out = ROOT / "docs/benchmark-report.md"
    out.write_text(md)
    print(md)
    print(f"report: {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prepare = sub.add_parser("prepare", help="下采样合成基准样本集")
    p_prepare.add_argument("--n-strains", type=int, default=4)
    p_prepare.add_argument("--reads", type=int, default=150_000)
    p_prepare.add_argument("--seed", type=int, default=11)
    p_prepare.set_defaults(func=cmd_prepare)

    p_run = sub.add_parser("run", help="跑基准（独立 workdir）")
    p_run.add_argument("--cores", type=int, default=15)
    p_run.add_argument("--reads-hint", type=int, default=150_000)
    p_run.set_defaults(func=cmd_run)

    p_ext = sub.add_parser("extrapolate", help="外推 96 株并渲染报告")
    p_ext.add_argument("--target-strains", type=int, default=96)
    p_ext.add_argument("--target-reads", type=int, default=1_000_000)
    p_ext.set_defaults(func=cmd_extrapolate)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
