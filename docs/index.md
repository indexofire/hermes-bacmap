# Hermes-bacmap

> **AI Native 病原微生物基因组智能分析平台** — 面向中小型疾控实验室的自然语言驱动 WGS 分析系统。

Hermes-bacmap 以 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 为编排核心，将 Snakemake 工作流、24 个生信工具、SQLite 数据模型与本地 LLM 推理整合为统一平台。用户用中文或英文自然语言即可完成从 FASTQ 上传到暴发溯源的全流程。

## 核心特性

- **自然语言交互** — "分析这株沙门菌"、"和上次暴发株比较 SNP"、"生成耐药报告"，Hermes Agent 自动路由到对应工具与技能。
- **四病原端到端** — Salmonella（全流程 + SNP 系统发育）、DEC/E. coli、Shigella/EIEC、V. parahaemolyticus，物种鉴定后自动路由到对应管线。
- **三层 AI 防御** — LLM 生成结果经 JSON Schema 校验 → Deterministic Verifier 确定性规则校验 → AI 解读，关键耐药基因（CTX-M/NDM/KPC/mcr-1）强制人工复核。
- **可追溯审计** — Genome Object Model (GOM) 以 SQLite + WAL + FTS5 存储所有结果，每个结论挂三元证据链 (strain_id, pipeline_version, database_versions)，对象不可变、版本化。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│              用户（自然语言 中文 / English）                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                 │   Hermes Agent      │   GLM-5.2 via Z.AI API
                 │   (LLM 编排层)       │   24 tools + 4 skills
                └──────────┬──────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                  │
┌────────▼───────┐ ┌───────▼────────┐ ┌──────▼─────────┐
│  L1 固定管线    │ │  L2 确定性校验   │ │  L3 AI 解读     │
│  Snakemake DAG │ │  Verifier       │ │  Skills + 搜索  │
│  23 rules      │ │  21 tests       │ │  FTS5 + 知识库  │
└────────┬───────┘ └───────┬────────┘ └──────┬─────────┘
         │                 │                  │
         └─────────────────┼──────────────────┘
                           │
                ┌──────────▼──────────┐
                │  Genome Object      │   SQLite + WAL + FTS5
                │  Model (GOM)        │   4 tables, 5 indexes
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │  本地文件系统         │   FASTQ / FASTA / VCF / BAM
                └─────────────────────┘
```

## 项目规模

| 维度 | 数量 | 说明 |
|---|---|---|
| Hermes Tools | **24** | 8 个生信原语 + 16 个高层分析工具 |
| Snakemake Rules | **24** | per-sample DAG + cohort SNP DAG（3 物种组） |
| 测试用例 | **994** | GOM + 溯源索引 + Verifier + Engine + Utils，全绿 |
| 支持病原 | **4** | Salmonella / DEC / Shigella / V. parahaemolyticus |
| Skills | **4** | bio-router / run-pipeline / interpret-results / bioinfo-analysis |
| 参考数据库 | **15** | 物种鉴定 + AMR + 毒力 + 血清型 + SNP 参考 + Prokka 注释 |

## 3 分钟快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/indexofire/hermes-bacmap.git
cd hermes-bacmap

# 2. 生信 CLI 工具 (pixi, 含 Python 3.12 + 全部依赖)
pixi install

# 3. 安装插件到 Hermes (entry-point 自动注册)
pip install -e . --python ~/.hermes/hermes-agent/venv/bin/python
hermes plugins enable hermes_bacmap

# 4. 验证安装
pixi run snakemake --version    # 应输出 7.32.x
uv run pytest -q                # 994 tests 全过

# 5. 启动 Hermes Agent
hermes chat
> 列出所有样本                    # bio_list_samples
> 分析 SAM-TYP-001               # 端到端流程
```

完整的硬件要求、依赖安装与数据库下载见 [环境准备](installation/environment.md) 与 [快速安装](installation/quick-start.md)。

## 接下来

| 章节 | 适合人群 | 内容 |
|---|---|---|
| [安装指南](installation/environment.md) | 运维 / 首次部署 | 硬件要求、uv + pixi 双环境、参考数据库 |
| [使用指南](usage/cli.md) | 实验室操作员 | CLI 脚本、Hermes Agent 对话、Web UI |
| [架构设计](architecture/overview.md) | 开发者 / 评估方 | 分层架构、Engine 引擎层、GOM 数据模型、Snakemake 管线 |
| [案例介绍](cases/single-sample.md) | 所有人 | 单株分析实战、7 株暴发调查 |
| [参考](reference/tools.md) | 开发者 | 18 工具清单、13 数据库、故障排查 |

!!! tip "首次使用?"
    建议顺序：[环境准备](installation/environment.md) → [快速安装](installation/quick-start.md) → [单株分析案例](cases/single-sample.md) → [Hermes Agent 交互](usage/hermes-agent.md)。
