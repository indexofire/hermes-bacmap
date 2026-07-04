# 批量监测：10 株混合样本

## 场景

例行监测批次，包含 10 株混合物种（如 Salmonella、DEC、Shigella/EIEC、V. parahaemolyticus）。
Hermes 自动根据物种标记基因将样本路由到对应分析管线。

## 标准操作流程

### 1. 批量分析

```bash
python scripts/run_analysis.py --all
```

- 自动读取 `workflows/salmonella/config/samples.tsv`
- 每个样本执行：QC → 组装 → 物种鉴定 → 血清型 / MLST / AMR / 毒力
- 构建 cohort-level SNP 树（Salmonella）

### 2. 结果入库

```bash
python scripts/ingest_results.py --all
```

- 将结果写入 GOM（Genome Object Model）
- 自动去重、版本管理、注册文件产物

### 3. 生成报告

```bash
python scripts/generate_report.py --all
```

- 为每株生成独立 HTML 报告
- 汇总 batch summary

## 状态监控

```bash
python scripts/run_analysis.py --status
```

查看每个样本当前处于哪一阶段（qc / assembly / species / typing / amr / report）。

## Hermes 自然语言查询示例

启动 `hermes chat` 后：

```
> 列出所有样本
> 哪些样本是 Typhimurium?
> 搜索 blaCTX
> SAM-DEC-012 的致病型是什么？
> 比较 SAM-SHI-013 和 SAM-EIEC-014
```

## 预期结果

- 自动物种路由：invA → Salmonella，uidA → DEC，ipaH → Shigella/EIEC，toxR/tlh → V. parahaemolyticus
- 无需人工指定物种
- 混合批次可在单条命令下完成端到端分析
