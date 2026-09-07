# 96-Strain Batch Benchmark

> 生成：`python scripts/benchmark_batch.py`（V0.7 Wave 4）。
> 线性外推模型：每株每读段成本恒定；§2.2 的 ≤8h 目标按推荐档（24c/48t）设定，
> 本机结果需按核数另行折算。

## Benchmark setup

- bench strains: **4** × 150,000 read pairs（seqkit 下采样自 gold standard）
- cores: **8**（AMD Ryzen 7 5700G，8c/16t）
- measured wall time: **550.0s**（0.15h）

## Extrapolation to 96 strains

- 96 株 × 1,000,000 read pairs @ 8 cores：**88000s ≈ 24.4h**
- vs 目标 ≤8h（推荐档 24c/48t）：❌ 不满足

## Notes

- SPAdes 装配是核心瓶颈（project.md §7.4）；浅深度下采样对外推偏乐观，
  全读深单株耗时更高，结论以全量跑为准。
- 基准跑批完全隔离：`samples_bench.tsv` + `results-bench/`，不触碰生产 results/。
