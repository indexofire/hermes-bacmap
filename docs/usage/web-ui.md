# Web UI

Hermes-bacmap 提供轻量 Web UI（FastAPI 后端 + 预编译静态前端），用于浏览分析结果、查看 SNP 树与检索样本。Web UI 只读，不触发新分析——分析仍走 [CLI](cli.md) 或 [Hermes Agent](hermes-agent.md)。

## 启动

```bash
# 默认端口 8080
uvicorn web.app:app --port 8080

# 开发模式（热重载）
uvicorn web.app:app --reload --port 8080

# 监听所有网卡
uvicorn web.app:app --host 0.0.0.0 --port 8080
```

浏览器打开 <http://localhost:8080>。

## 页面

Web UI 共 5 个页面：

### 1. Dashboard（仪表盘）

`GET /`

总览：样本数、完成数、进行中、未开始；SNP cohort 是否就绪。每株一行卡片，显示样本编号、检出物种、MLST ST、血清型、状态徽章。

### 2. Sample Detail（样本详情）

点击任一样本进入详情页。展示该样本完整 `summary.json`：

- QC 统计（fastp before/after filtering）
- 组装统计（N50、contig 数、总长、GC%）
- 物种鉴定结果（invA/uidA/ipaH 命中详情）
- MLST（scheme + ST + 等位基因型）
- 血清型（SISTR / ecoh / shigella 分流后的主血清型）
- AMR / 毒力 / 质粒基因列表（CARD / VFDB / PlasmidFinder）
- 注释统计（CDS 数、注释率）

### 3. SNP Tree（系统发育树）

展示 cohort 级 SNP 分析结果：

- IQ-TREE Newick 树的可视化渲染
- 两两 SNP 距离矩阵（heatmap）
- 关键统计：SNP 位点数、缺失率、bootstrap 支持

阈值参考（来自 `interpret-results` skill）：

| SNP 距离 | 解读 |
|---|---|
| 0–5 | 同源传播链（高度相关） |
| 6–15 | 可能有流行病学关联 |
| 16–50 | 同一谱系 |
| >50 | 不同谱系 |

### 4. Search（样本检索）

自然语言检索已入库样本，复用 `bio_search_samples` 的字段加权策略：

```
搜索框输入：Typhimurium
→ 命中 serotype 精确匹配（score=10）
→ 返回 SAM-TYP-001、SAM-TYP-002
```

支持搜血清型、MLST ST、AMR 基因名、质粒名、物种名、样本编号。

### 5. About（关于）

项目信息、版本、支持的病原、文档链接。

## API 端点

Web UI 后端暴露以下 REST API，可供脚本或第三方集成调用：

| 方法 | 路径 | 说明 | 示例响应字段 |
|---|---|---|---|
| GET | `/api/status` | 管线总状态 | `total_samples`, `completed`, `in_progress`, `not_started`, `snp_available` |
| GET | `/api/samples` | 全部样本列表 + 状态 | `samples[]`: `sample_id`, `species_detected`, `mlst_st`, `serotype`, `status` |
| GET | `/api/samples/{sample_id}` | 单株完整 summary | `steps`: qc / assembly_stats / species / mlst / serotype / amr |
| GET | `/api/samples/{sample_id}/annotation` | 单株注释 | CDS 列表、注释率、hypothetical 数 |
| GET | `/api/snp` | SNP cohort 汇总 | `tree_newick`, `pairwise_distances`, `n_snp_sites`, `missing_rate` |
| GET | `/api/search?q={query}` | 自然语言检索 | 匹配样本列表 + 匹配字段 + 相关度分数 |

### 调用示例

```bash
# 管线状态
curl http://localhost:8080/api/status
# {"total_samples":10,"completed":8,"in_progress":1,"not_started":1,"snp_available":true}

# 单株结果
curl http://localhost:8080/api/samples/SAM-TYP-001 | python -m json.tool

# 搜索
curl "http://localhost:8080/api/search?q=CTX-M"
```

所有 API 返回 JSON，可直接被其他工具或 LLM Agent 消费。

## 前端开发（可选）

前端静态资源已预编译到 `web/static/` 与 `web/templates/`，无需 Node.js 即可运行。如需修改前端：

```bash
# 需要 Node.js 18+
cd web/frontend       # 前端源码目录（若存在）
npm install
npm run build         # 输出到 web/static/
```

后端 `web/app.py` 通过 FastAPI `StaticFiles` 挂载 `/static`，`/` 路由返回 `templates/index.html`。

## 限制

- Web UI 当前**只读**，不支持从浏览器发起分析（设计上保持分析入口单一：CLI 或 Agent）
- 无鉴权，仅适合本地或内网部署；公网暴露前请加反向代理 + 鉴权
- SNP 树渲染依赖前端 JS，弱网下首次加载较慢

后续计划（V1.0+）：增加提交流水线任务、用户认证、多队列管理。
