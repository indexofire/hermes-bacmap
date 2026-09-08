"""TDD 测试：scripts/benchmark_batch.py（V0.7 Wave 4，project.md §2.2 96 株 ≤8h）。

纯函数部分：外推模型（按株数 × 读段数线性缩放，同核数）、samples_bench.tsv
构造、报告渲染。真实跑批（seqkit 下采样 + Snakemake）不在单测范围。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
for _p in (_PROJECT_ROOT / "scripts", _PROJECT_ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_SPEC = importlib.util.spec_from_file_location(
    "benchmark_batch", _PROJECT_ROOT / "scripts" / "benchmark_batch.py"
)
assert _SPEC is not None and _SPEC.loader is not None
benchmark_batch = importlib.util.module_from_spec(_SPEC)
sys.modules["benchmark_batch"] = benchmark_batch
_SPEC.loader.exec_module(benchmark_batch)

import pytest  # noqa: E402


class TestExtrapolate:
    def test_linear_scaling_by_strains_and_reads(self):
        est = benchmark_batch.extrapolate(
            measured_seconds=600.0,
            bench_strains=4,
            bench_reads_per_strain=150_000,
            target_strains=96,
            target_reads_per_strain=1_000_000,
        )
        # 每株每读段成本 × 96 株 × (1M/150k)：600/4/150k × 96 × 1M = 96000s
        assert est.target_seconds == pytest.approx(96_000.0)
        assert est.target_hours == pytest.approx(96_000 / 3600)

    def test_same_size_returns_measured(self):
        est = benchmark_batch.extrapolate(600.0, 4, 150_000, 4, 150_000)
        assert est.target_seconds == pytest.approx(600.0)

    def test_meets_target_flag(self):
        ok = benchmark_batch.extrapolate(600.0, 4, 150_000, 96, 150_000)
        slow = benchmark_batch.extrapolate(600.0, 4, 150_000, 96, 1_000_000)
        assert ok.meets_8h_target is True
        assert slow.meets_8h_target is False


class TestBenchTsv:
    def test_rows_render_tsv(self):
        tsv = benchmark_batch.render_samples_tsv(
            [
                ("BEN-001", "Salmonella", "/abs/r1.fastq.gz", "/abs/r2.fastq.gz"),
                ("BEN-002", "Salmonella", "/abs/b1.fastq.gz", "/abs/b2.fastq.gz"),
            ]
        )
        lines = tsv.strip().splitlines()
        assert lines[0] == "sample\tspecies\tR1\tR2"
        assert lines[1].startswith("BEN-001\tSalmonella\t/abs/r1.fastq.gz")
        assert len(lines) == 3


class TestRenderReport:
    def test_markdown_sections(self):
        est = benchmark_batch.extrapolate(600.0, 4, 150_000, 96, 1_000_000)
        md = benchmark_batch.render_benchmark_md(
            bench_strains=4,
            bench_reads=150_000,
            cores=15,
            measured_seconds=600.0,
            estimate=est,
            target_strains=96,
            target_reads=1_000_000,
        )
        assert "## Benchmark setup" in md
        assert "## Extrapolation to 96 strains" in md
        assert "96000.0s" in md or "26.7" in md  # hours 或秒呈现其一
        assert "≤8h" in md

    def test_target_params_rendered_not_hardcoded(self):
        """P2-5：目标株数/读段数来自参数而非硬编码文本。"""
        est = benchmark_batch.extrapolate(600.0, 4, 150_000, 48, 500_000)
        md = benchmark_batch.render_benchmark_md(
            bench_strains=4,
            bench_reads=150_000,
            cores=8,
            measured_seconds=600.0,
            estimate=est,
            target_strains=48,
            target_reads=500_000,
            timing_source="synthetic_conservative",
        )
        assert "48 株 × 500,000" in md
        assert "96 株" not in md
        assert "`synthetic_conservative`" in md
