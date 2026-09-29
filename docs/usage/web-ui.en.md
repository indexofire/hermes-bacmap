# Web UI

Hermes-bacmap ships a lightweight Web UI (FastAPI backend + prebuilt static frontend) for browsing analysis
results, viewing the SNP tree, and searching samples. The Web UI is read-only and does not trigger new
analyses — analysis still goes through the [CLI](cli.md) or the [Hermes Agent](hermes-agent.md).

## Starting

```bash
# 默认端口 8080
uvicorn web.app:app --port 8080

# 开发模式（热重载）
uvicorn web.app:app --reload --port 8080

# 监听所有网卡
uvicorn web.app:app --host 0.0.0.0 --port 8080
```

Open <http://localhost:8080> in a browser.

## Pages

The Web UI has 5 pages:

### 1. Dashboard

`GET /`

Overview: sample count, completed, in progress, not started; whether the SNP cohort is ready. One card row per isolate showing the sample ID, detected species, MLST ST, serotype, and a status badge.

### 2. Sample Detail

Click any sample to open its detail page. It shows the sample's complete `summary.json`:

- QC statistics (fastp before/after filtering)
- Assembly statistics (N50, contig count, total length, GC%)
- Species identification results (invA/uidA/ipaH hit details)
- MLST (scheme + ST + allele profile)
- Serotype (primary serotype after SISTR / ecoh / shigella routing)
- AMR / virulence / plasmid gene lists (CARD / VFDB / PlasmidFinder)
- Annotation statistics (CDS count, annotation rate)

### 3. SNP Tree (phylogenetic tree)

Shows the cohort-level SNP analysis results:

- Visual rendering of the IQ-TREE Newick tree
- Pairwise SNP distance matrix (heatmap)
- Key statistics: SNP site count, missing rate, bootstrap support

Threshold reference (from the `interpret-results` skill):

| SNP distance | Interpretation |
|---|---|
| 0–5 | Common-source transmission chain (highly related) |
| 6–15 | Possible epidemiological link |
| 16–50 | Same lineage |
| >50 | Different lineages |

### 4. Search

Natural-language search over ingested samples, reusing the field-weighting strategy of `bio_search_samples`:

```
搜索框输入：Typhimurium
→ 命中 serotype 精确匹配（score=10）
→ 返回 SAM-TYP-001、SAM-TYP-002
```

Supports searching by serotype, MLST ST, AMR gene name, plasmid name, species name, and sample ID.

### 5. About

Project information, version, supported pathogens, and documentation links.

## API Endpoints

The Web UI backend exposes the following REST APIs, which scripts or third-party integrations can call:

| Method | Path | Description | Example response fields |
|---|---|---|---|
| GET | `/api/status` | Overall pipeline status | `total_samples`, `completed`, `in_progress`, `not_started`, `snp_available` |
| GET | `/api/samples` | All samples list + status | `samples[]`: `sample_id`, `species_detected`, `mlst_st`, `serotype`, `status` |
| GET | `/api/samples/{sample_id}` | Full per-isolate summary | `steps`: qc / assembly_stats / species / mlst / serotype / amr |
| GET | `/api/samples/{sample_id}/annotation` | Per-isolate annotation | CDS list, annotation rate, hypothetical count |
| GET | `/api/snp` | SNP cohort summary | `tree_newick`, `pairwise_distances`, `n_snp_sites`, `missing_rate` |
| GET | `/api/search?q={query}` | Natural-language search | Matching sample list + matched field + relevance score |

### Example Calls

```bash
# 管线状态
curl http://localhost:8080/api/status
# {"total_samples":10,"completed":8,"in_progress":1,"not_started":1,"snp_available":true}

# 单株结果
curl http://localhost:8080/api/samples/SAM-TYP-001 | python -m json.tool

# 搜索
curl "http://localhost:8080/api/search?q=CTX-M"
```

All APIs return JSON and can be consumed directly by other tools or LLM agents.

## Frontend Development (optional)

Frontend static assets are prebuilt into `web/static/` and `web/templates/`; Node.js is not required to run. To modify the frontend:

```bash
# 需要 Node.js 18+
cd web/frontend       # 前端源码目录（若存在）
npm install
npm run build         # 输出到 web/static/
```

The backend `web/app.py` mounts `/static` via FastAPI `StaticFiles`; the `/` route returns `templates/index.html`.

## Limitations

- The Web UI is currently **read-only** and cannot launch analyses from the browser (by design, analysis entry points stay unified: CLI or Agent)
- No authentication; suitable only for local or intranet deployment — add a reverse proxy + auth before exposing it publicly
- SNP tree rendering depends on frontend JS; the first load can be slow on weak networks

Future plans (V1.0+): submitting pipeline jobs, user authentication, multi-queue management.
