# GBrain 知识大脑层

> **状态**: 已安装 v0.42.57.0 · PGLite 模式 · MCP 接入 Hermes

---

## 概述

[GBrain](https://github.com/garrytan/gbrain) 是 Garry Tan（YC CEO）开发的知识大脑系统，25.2K stars，生产环境运行 146K 页面。在本项目中替代 project.md §8.3 规划的三层 RAG 架构。

### 与 hermes-bacmap 的关系

```
┌──────────────────────────────────────────┐
│            Hermes Agent (LLM)            │
├───────────┬──────────────────────────────┤
│           │                              │
│  hermes_bacmap     GBrain               │
│  (插件层)          (平台层)              │
│  18 bio tools      30+ MCP tools        │
│  GOM (SQLite)      Knowledge (PGLite)   │
│  "样本有什么"      "这意味着什么"        │
└───────────┴──────────────────────────────┘
```

GBrain 接入 Hermes **平台层**（非 hermes-bacmap 插件层），hermes-bacmap 零改动。

---

## 安装

### 前置条件

- Bun >= 1.2.x
- Ollama（本地 embedding，可选但推荐）

### 步骤

```bash
# 1. 安装 Bun
curl -fsSL https://bun.sh/install | bash
export PATH="$HOME/.bun/bin:$PATH"

# 2. 安装 GBrain
git clone --depth 1 https://github.com/garrytan/gbrain.git ~/gbrain
cd ~/gbrain && bun install
ln -sf ~/gbrain/src/cli.ts ~/.bun/bin/gbrain
chmod +x ~/gbrain/src/cli.ts

# 3. 验证
gbrain --version  # 应输出 gbrain 0.42.x.x
```

### 初始化

```bash
# 方式 A: 本地 embedding（推荐，零成本）
ollama pull nomic-embed-text
gbrain init --pglite \
  --embedding-model ollama:nomic-embed-text \
  --embedding-dimensions 768

# 方式 B: 云端 embedding
export ZEROENTROPY_API_KEY=ze-...
gbrain init --pglite \
  --embedding-model zeroentropyai:zembed-1

# 方式 C: 延迟配置
gbrain init --pglite --no-embedding
```

### 导入知识

```bash
gbrain import ~/repo/github/hermes-bacmap/skills/interpret-results/
gbrain import ~/repo/github/hermes-bacmap/skills/interpret-results/references/
gbrain import ~/repo/github/hermes-bacmap/skills/run-pipeline/references/
```

---

## 连接 Hermes

### MCP stdio（本地）

```bash
gbrain serve  # Hermes 自动发现
```

### 配置文件方式

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  gbrain:
    command: gbrain
    args: ["serve"]
```

### 验证

```bash
gbrain doctor          # 健康检查
gbrain list -n 10      # 查看已导入页面
gbrain search "blaCTX-M"  # 关键词搜索
```

---

## 使用

### 关键词搜索（无 embedding 也可用）

```bash
gbrain search "Salmonella serotype threshold"
gbrain search "碳青霉烯耐药"
```

### 综合回答（需要 embedding）

```bash
gbrain think "blaCTX-M-15 在沙门菌中的临床意义是什么？"
```

返回：综合答案 + 引用来源 + 缺口分析（标注哪些信息缺失）。

### 通过 Hermes Agent

```
hermes chat
> SAM-TYP-001 检出了 blaCMY-2，临床意义是什么？
```

LLM 自动编排：
1. `bio_get_result("SAM-TYP-001")` → 事实（hermes-bacmap）
2. `gbrain think("blaCMY-2 临床意义")` → 知识（GBrain）
3. 综合两者 → 完整解读

---

## Embedding 模型

| Provider | 模型 | 维度 | VRAM | 成本 | 配置 |
|---|---|---|---|---|---|
| **Ollama** | nomic-embed-text | 768 | ~300MB | 免费 | `ollama:nomic-embed-text` |
| **Ollama** | mxbai-embed-large | 1024 | ~670MB | 免费 | `ollama:mxbai-embed-large` |
| **Ollama** | all-minilm | 384 | ~120MB | 免费 | `ollama:all-minilm` |
| **llama.cpp** | 任意 GGUF | 用户指定 | 取决于模型 | 免费 | `llama-server:<id>` |
| OpenAI | text-embedding-3-small | 1536 | 0 | $0.02/1M | `openai:text-embedding-3-small` |
| OpenAI | text-embedding-3-large | 1536 | 0 | $0.13/1M | `openai:text-embedding-3-large` |
| ZeroEntropy | zembed-1 | 2560 | 0 | $0.05/1M | `zeroentropyai:zembed-1` |
| Voyage | voyage-3-large | 1024 | 0 | $0.18/1M | `voyage:voyage-3-large` |

### 切换 embedding 模型

```bash
# 切换到不同维度需要重新初始化
gbrain init --force --pglite \
  --embedding-model ollama:mxbai-embed-large \
  --embedding-dimensions 1024

# 重新导入（生成新向量）
gbrain import ~/repo/github/hermes-bacmap/skills/
```

---

## 已导入的知识内容

| GBrain 页面 | 来源文件 | 内容 |
|---|---|---|
| interpret-results (skill) | skills/interpret-results/SKILL.md | 血清型/MLST/AMR/SNP/毒力基因解读 |
| amr-gene-reference | interpret-results/references/ | β-内酰胺酶分级 + 临床优先级 + 报告语言 |
| snp-distance-thresholds | interpret-results/references/ | 暴发判定阈值 + 读树指南 + 调查流程 |
| salmonella | run-pipeline/references/ | invA/SISTR/gmlst/SNP 参考 |
| dec-shigella | run-pipeline/references/ | ecoh/shigella_serotyper/pathotype |
| vpara | run-pipeline/references/ | toxR/tlh/tdh/trh |
| pipeline-params | run-pipeline/references/ | Snakemake 参数 + 质量阈值 + 耗时 |
| troubleshooting | run-pipeline/references/ | 常见错误 + 修复步骤 |

### 持续积累

```bash
# 捕获新知识
gbrain capture "实验室 X 发现 ST34 monophasic Typhimurium 携带 mcr-1"

# 导入文献/指南
gbrain import ~/documents/AMR-guidelines-2026/

# 导入 PDF（需要 OCR skill）
gbrain capture --file ~/documents/outbreak-report.pdf
```

---

## 替代 project.md §8.3 的映射

| §8.3 原计划 | GBrain 实现 |
|---|---|
| Layer 1: Source of Truth (SQL 精确查询) | **GOM 不变**（SQLite） |
| Layer 2: 知识图谱 (Apache AGE + Cypher) | **GBrain 自连线图谱**（零 LLM 自动建边） |
| Layer 3: 向量库 (sqlite-vec + BM25) | **GBrain 混合搜索**（HNSW + BM25 + RRF + reranker） |
| 综合 synthesis prompt | **GBrain think**（内置综合 + 引用 + 缺口分析） |
| 夜间维护脚本 | **GBrain cron**（自动去重/修复/评分/矛盾发现） |

---

## 故障排查

| 问题 | 修复 |
|---|---|
| `gbrain: command not found` | `export PATH="$HOME/.bun/bin:$PATH"` |
| `No embedding provider configured` | `ollama pull nomic-embed-text` + 重新 `gbrain init --force` |
| `PGLite schema_version: 0` | `gbrain apply-migrations --yes` |
| `gbrain serve` 无响应 | 确认 Ollama 在运行：`ollama serve &` |
| 搜索结果为空 | 检查导入：`gbrain list -n 20` |
