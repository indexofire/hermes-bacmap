# GBrain Knowledge Brain Layer

> **Status**: v0.42.57.0 installed · PGLite mode · MCP-connected to Hermes

---

## Overview

[GBrain](https://github.com/garrytan/gbrain) is a knowledge brain system developed by Garry Tan (YC CEO), 25.2K stars,
running 146K pages in production. In this project it replaces the three-layer RAG architecture planned in project.md §8.3.

### Relationship to hermes-bacmap

```
┌──────────────────────────────────────────┐
│            Hermes Agent (LLM)            │
├───────────┬──────────────────────────────┤
│           │                              │
│  hermes_bacmap     GBrain               │
│  (plugin layer)    (platform layer)     │
│  18 bio tools      30+ MCP tools        │
│  GOM (SQLite)      Knowledge (PGLite)   │
│  "what the sample  "what it means"      │
│   has"                                   │
└───────────┴──────────────────────────────┘
```

GBrain plugs into the Hermes **platform layer** (not the hermes-bacmap plugin layer); hermes-bacmap requires zero changes.

---

## Installation

### Prerequisites

- Bun >= 1.2.x
- Ollama (local embeddings, optional but recommended)

### Steps

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

### Initialization

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

### Importing knowledge

```bash
gbrain import ~/repo/github/hermes-bacmap/skills/interpret-results/
gbrain import ~/repo/github/hermes-bacmap/skills/interpret-results/references/
gbrain import ~/repo/github/hermes-bacmap/skills/run-pipeline/references/
```

---

## Connecting to Hermes

### MCP stdio (local)

```bash
gbrain serve  # Hermes 自动发现
```

### Config-file approach

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  gbrain:
    command: gbrain
    args: ["serve"]
```

### Verification

```bash
gbrain doctor          # 健康检查
gbrain list -n 10      # 查看已导入页面
gbrain search "blaCTX-M"  # 关键词搜索
```

---

## Usage

### Keyword search (works without embeddings)

```bash
gbrain search "Salmonella serotype threshold"
gbrain search "碳青霉烯耐药"
```

### Synthesized answers (embeddings required)

```bash
gbrain think "blaCTX-M-15 在沙门菌中的临床意义是什么？"
```

Returns: a synthesized answer + cited sources + gap analysis (flagging which information is missing).

### Via the Hermes Agent

```
hermes chat
> SAM-TYP-001 detected blaCMY-2 — what is the clinical significance?
```

The LLM orchestrates automatically:
1. `bio_get_result("SAM-TYP-001")` → facts (hermes-bacmap)
2. `gbrain think("blaCMY-2 clinical significance")` → knowledge (GBrain)
3. Synthesize both → complete interpretation

---

## Embedding Models

| Provider | Model | Dimensions | VRAM | Cost | Config |
|---|---|---|---|---|---|
| **Ollama** | nomic-embed-text | 768 | ~300MB | Free | `ollama:nomic-embed-text` |
| **Ollama** | mxbai-embed-large | 1024 | ~670MB | Free | `ollama:mxbai-embed-large` |
| **Ollama** | all-minilm | 384 | ~120MB | Free | `ollama:all-minilm` |
| **llama.cpp** | any GGUF | user-specified | model-dependent | Free | `llama-server:<id>` |
| OpenAI | text-embedding-3-small | 1536 | 0 | $0.02/1M | `openai:text-embedding-3-small` |
| OpenAI | text-embedding-3-large | 1536 | 0 | $0.13/1M | `openai:text-embedding-3-large` |
| ZeroEntropy | zembed-1 | 2560 | 0 | $0.05/1M | `zeroentropyai:zembed-1` |
| Voyage | voyage-3-large | 1024 | 0 | $0.18/1M | `voyage:voyage-3-large` |

### Switching embedding models

```bash
# 切换到不同维度需要重新初始化
gbrain init --force --pglite \
  --embedding-model ollama:mxbai-embed-large \
  --embedding-dimensions 1024

# 重新导入（生成新向量）
gbrain import ~/repo/github/hermes-bacmap/skills/
```

---

## Imported Knowledge Content

| GBrain page | Source file | Content |
|---|---|---|
| interpret-results (skill) | skills/interpret-results/SKILL.md | Serotype/MLST/AMR/SNP/virulence-gene interpretation |
| amr-gene-reference | interpret-results/references/ | β-lactamase tiers + clinical priorities + reporting language |
| snp-distance-thresholds | interpret-results/references/ | Outbreak determination thresholds + tree-reading guide + investigation workflow |
| salmonella | run-pipeline/references/ | invA/SISTR/gmlst/SNP reference |
| dec-shigella | run-pipeline/references/ | ecoh/shigella_serotyper/pathotype |
| vpara | run-pipeline/references/ | toxR/tlh/tdh/trh |
| pipeline-params | run-pipeline/references/ | Snakemake parameters + quality thresholds + runtimes |
| troubleshooting | run-pipeline/references/ | Common errors + fix procedures |

### Continuous accumulation

```bash
# 捕获新知识
gbrain capture "实验室 X 发现 ST34 monophasic Typhimurium 携带 mcr-1"

# 导入文献/指南
gbrain import ~/documents/AMR-guidelines-2026/

# 导入 PDF（需要 OCR skill）
gbrain capture --file ~/documents/outbreak-report.pdf
```

---

## Mapping to the Replaced project.md §8.3

| §8.3 original plan | GBrain implementation |
|---|---|
| Layer 1: Source of Truth (exact SQL queries) | **GOM unchanged** (SQLite) |
| Layer 2: knowledge graph (Apache AGE + Cypher) | **GBrain auto-linked graph** (zero-LLM automatic edge creation) |
| Layer 3: vector store (sqlite-vec + BM25) | **GBrain hybrid search** (HNSW + BM25 + RRF + reranker) |
| Synthesis prompt | **GBrain think** (built-in synthesis + citations + gap analysis) |
| Nightly maintenance scripts | **GBrain cron** (automatic dedup/repair/scoring/contradiction discovery) |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `gbrain: command not found` | `export PATH="$HOME/.bun/bin:$PATH"` |
| `No embedding provider configured` | `ollama pull nomic-embed-text` + re-run `gbrain init --force` |
| `PGLite schema_version: 0` | `gbrain apply-migrations --yes` |
| `gbrain serve` unresponsive | Confirm Ollama is running: `ollama serve &` |
| Empty search results | Check imports: `gbrain list -n 20` |
