# 代码质量评估与修复路线

> 评估日期：2026-07-18 · 评估基线：V0.5.0(commit `844d058`)· 执行方式：全量代码阅读 + 质量工具实测(ruff / mypy --strict / pytest --cov)

## 一、总体结论

项目架构设计意识高于平均水平：分层清晰、GOM 持久层建模认真（不可变对象 + 版本链 + 事件溯源）、services 层测试覆盖良好。但评估时发现**质量门禁已全线失守**——lint 失败、mypy 启动即崩、覆盖率 80% 门禁实际仅 28%,CI 配置与 `requires-python` 矛盾，且存在从未运行过的损坏代码分支。

经过三个阶段的集中修复，当前所有质量门禁恢复真实有效，并顺带修复了 8 组真实 bug(含 2 组影响分析结论正确性的高危 bug)。

**评分(评估时)→(修复后)**

| 维度 | 评估时 | 修复后 |
|---|---|---|
| 架构 | 7.5/10 | 8.5/10（阶段 3 结构重构完成：上帝模块拆分、循环依赖破除、共用层抽取） |
| 代码质量 | 5/10 | 9/10（门禁全绿，覆盖 92.21%) |

## 二、架构评估

### 分层结构

```
tools/              LLM 门面层(24 个 tool handler,按 seq/cli/pipeline/services 分包,JSON in/out)
    ↓ 懒加载
analysis/           算法层(gene_scanner, species_identifier, verifier…)
    ↓
engine/             CLI 抽象层(SequenceMatcher/ReadMapper + 后端注册表)
    ↓
backends/           blast / minimap2 / kma / mash / sourmash
services/           持久层(GOM + strain_index + metadata + lab_results + sample_summary,独立无依赖)
```

### 架构优点

- `engine/` 抽象层：`Registry` 懒加载后端,`SequenceMatcher` 按查询大小自动选后端(>10MB → minimap2),pipeline 逻辑与具体 CLI 工具解耦。
- `services/genome_object_service.py`:frozen dataclass 强制不可变、semver 校验、证据链(pipeline_version + database_versions)在 `__post_init__` 强制、SQLite WAL + FTS5,设计与 project.md §4/§5 互相引用可追溯。
- tool handler "永不抛异常、错误转 JSON" 的约定对 LLM 场景是正确设计。
- 参考数据库路径集中在 `db.py` 注册表,`config.py` 支持环境变量覆盖。

### 架构问题(已全部处理,2026-07-18)

| 问题 | 位置 | 状态 |
|---|---|---|
| 上帝模块 1887 行，24 个 handler 单文件 | `tools.py` | ✅ 已拆分为 `tools/` 包(seq / cli / pipeline / services + `_common` + `registry`),并引入 `@tool_handler` 统一错误兜底 |
| 1012 行引擎类，含嵌套闭包，难单测 | `typing/vpa_serotyper_engine.py` | ✅ 已拆分为 `_vpa_kmer` / `_vpa_genes` / `_vpa_report` + 430 行编排 facade,6 个闭包收敛为纯函数,6 处全库扫描收敛为 `_RefFasta` 缓存 |
| 软循环依赖(互相懒加载) | `species_identifier ↔ taxonomic_validator` | ✅ 已破环:删除 `identify(mode="standard")` 透传分支,依赖单向化 |
| 子包 `__init__.py` 全空，无 `__all__` | `analysis/ services/ typing/` | ✅ 已补导出 + `__all__` |
| 样本状态判定逻辑两处重复 | `scripts/run_analysis.py`、`web/app.py` | ✅ 已抽取为 `services/sample_summary.py` 共用层 |
| 24 段重复注册代码 | `__init__.py:register()` | ✅ 已改为 `tools/registry.py` 单张注册表 + for 循环(28 行) |

## 三、评估时实测数据(2026-07-18 修复前基线)

| 门禁 | 配置 | 实测 | 判定 |
|---|---|---|---|
| ruff check + format | 全绿 | 29 个错误 + 24 个文件未格式化 | ❌ |
| mypy --strict | 0 错误 | 启动即崩(mappy/sourmash stub 缺失 + Python 版本错配),**从未真正分析过业务代码**;修复启动问题后暴露 203 个错误 | ❌ |
| pytest 覆盖率 | `fail_under = 80` | **28.35%** | ❌ |
| CI python-version | 3.12(requires-python) | 全部 job 用 3.11,`pip install -e .` 必失败 | ❌ |

覆盖率断层(修复前):services 83–93% vs `tools.py` 4%、`typing/` 全部 0%、`engine/backends/` 0%。

## 四、修复实施记录

### 阶段 0 — 门禁恢复(2026-07-18)

1. Python 版本统一 3.12(pyproject ruff/mypy target、ci.yml × 5、test_env.py 断言)。
2. mypy overrides 补 `mappy`/`sourmash`;修复全部 203 个类型错误(真实注解，仅剩 9 个带具体错误码的 `type: ignore`,全部用于无 stub 的 Biopython 调用)。
3. `ruff check --fix` + `ruff format` 全量修复。
4. 合并 `test_engine.py` 重复定义同名测试类(此前一个类的测试被静默吞没)。
5. 生成 `.secrets.baseline`(排除 `data/` 生物序列高熵误报),pre-commit detect-secrets 恢复可用。
6. 删除 `engine/backends/kmer.py` 22 行 `return` 后的不可达死代码。

### 阶段 1 — 已确认 bug 修复 + 重复收敛(2026-07-18)

- **修复 `_scan_reads` FASTQ 分支 3 处必崩点**(`gene_scanner.py`):`ScanResult(query=…)` 字段不存在、`GeneHit(evalue=/depth=)` 字段不存在、`result.all_hits` 属性不存在——该分支此前从未能运行。
- 修复 `typing/vpa_serotyper.py` 跨模块私有导入 `_PROJECT_ROOT` → 改从 `config` 正式导入。
- **MLST 解析 7 处 → `utils.parse_mlst` 单一实现**(deterministic_verifier、tools.get_result、
  tools.search_samples、strain_index、web/app.py、run_analysis.py);其中 web/app.py 与
  run_analysis.py 原实现取错列(返回最后一个等位基因而非 ST),随收敛一并修复。
- `which`/`pixi_path` 重复定义收敛:`engine/_env.py` 改为从 `config.py` 转出口，调用方零改动。
- `tools.py` 21 处裸 `except Exception` 补 `logger.exception`(17 处新增 + 既有 4 处),异常不再静默吞没。

### 阶段 2 — 覆盖率达标(2026-07-18)

新增约 750 个单元测试(4 个并行工作流按模块边界实施):parser 类用静态样例文本、CLI 边界全部 mock(测试在无二进制环境可运行)、handler 类 mock subprocess + tmp SQLite 真实服务层。

| 模块 | 修复前 | 修复后 |
|---|---|---|
| `tools.py` | 4% | 92% |
| `engine/`(整体) | 0–39% | 92–100% |
| `analysis/`(整体) | 15–56% | 90–100% |
| `typing/`(除 vpa_engine) | 0% | 83–100% |
| `typing/vpa_serotyper_engine.py` | 0% | 49% |
| `db.py` / `schemas.py` | 0% / 100% | 100% / 100% |
| **总计** | **28.35%** | **86.07% → 90.26%**(修 bug 后) |

### 测试驱动发现的 5 组生产 bug(已全部修复)

| # | 位置 | 问题与修法 |
|---|---|---|
| 1 🔴 | `analysis/species_identifier.py` | `identify()` 键小写化后用混合大小写探测,**Salmonella/DEC/Shigella/toxR 鉴定永不触发**。修复:删除重复 if 链,改查 `_SPECIES_PRIORITY` + `_GENE_TO_SPECIES` 表(单一数据源)。 |
| 2 🔴 | `typing/shigella_serotyper.py` | `_FLEXNERI_RULES` 按序短路,medium 子集规则抢在精确规则前命中,**11+ 个血清型误判**(1b/1c/2b/2av/4av/5b/7b/Xv/3a/4b/4bv)。修复:两段制——先全体精确匹配(high),再无匹配做近匹配(medium,更具体规则优先)。 |
| 3 🟡 | `analysis/failure_diagnostics.py` | 正则 `\\.nhr`/`\\.phr`/`\\.pixi` 要求字面反斜杠。修复:改 `\.`。 |
| 4 🟡 | `analysis/failure_diagnostics.py` | 未知错误 exit code 被"最后 3 行"兜底覆盖。修复:改为追加。 |
| 5 🟢 | `tools.py:seq_convert` | `_resolve_path('')` 返回 CWD 导致 output_file 校验失效。修复:resolve 前判空。 |

## 五、当前质量门禁状态(2026-07-18,结构重构后)

```
ruff check src/ tests/        ✅ All checks passed
ruff format --check           ✅ 80 files already formatted
mypy --strict src/            ✅ Success: no issues found in 44 source files
pytest tests/                 ✅ 1051 passed
coverage (branch, fail_under=80) ✅ 92.41%
```

## 六、遗留事项(阶段 3 路线图)

按建议优先级排序:

1. ~~**提交保护成果**~~ ✅(2026-07-18 完成):拆为 4 个原子提交 —— `12cd7e9` 配置门禁、`d5a4525` bug 修复 + 收敛、`a828d7e` 测试扩充、`be2c59b` 评估文档。
2. ~~**小重复收敛**~~ ✅(2026-07-18 完成):`kma._parse_template` 与 `gene_scanner._parse_db_header` 的 `~~~` header 解析合并为 `utils.parse_db_header` 单一实现,两处保留薄委托。
3. ~~**文档对账**~~ ✅(2026-07-18 完成):工具数统一为 24(7 处 17/19/23 矛盾)、测试数 193 → 994、README/overview/features 模块行数表按实测更新、
   rules 数统一为 24(10 个 .smk 共 23 rules + Snakefile `rule all`)、修复 7 处死链、`tools.md`/`features.md` 补齐漏列的 5–7 个工具。
4. ~~**sourmash 弃用 API 迁移**~~ ✅(2026-07-18 完成):`load_signatures` → `load_file_as_signatures`,`save_signatures` → `SaveSignaturesToLocation`;
   45 条 deprecation warning 全部消除(套件仅剩 1 条 fastapi 第三方 warning)。
5. ~~**结构重构**~~ ✅(2026-07-18 完成):`tools.py` 拆分为 `tools/` 包(seq / cli / pipeline / services + `_common` 共享基座 + `@tool_handler` 统一错误兜底,
   顺带补齐 5 个无保护 handler)+ `tools/registry.py` 表驱动注册;`vpa_serotyper_engine.py` 按 kmer 排名 / 基因验证 / 报告生成拆分为
   `_vpa_kmer` / `_vpa_genes` / `_vpa_report`(6 个闭包收敛为纯函数,6 处全库扫描收敛为 `_RefFasta` 缓存,删除死属性),
   engine 瘦身为 430 行编排 facade 并保留私有方法委托兼容测试;样本状态逻辑抽取为 `services/sample_summary.py` 供 scripts 与 web 共用;
   `species_identifier → taxonomic_validator` 循环依赖破环;子包补 `__init__.py` 导出 + `__all__`。`schemas.py` 保持单文件不动(纯数据,无拆分收益)。
6. ~~**集成测试**~~ ✅(2026-07-18 完成):`web/app.py` 补 13 个 FastAPI TestClient 冒烟测试(状态/详情/注释/SNP/搜索/元数据/实验室结果路由);
   新增 `test_vpa_e2e.py` 端到端测试 5 个(RIMD 2210633 真实基因组 → O3:K6 Perfect,Salmonella/E.coli 阴性对照);
   CI 新增 `snakemake-dag` job 并安装 web extra 使冒烟测试入流水线。
