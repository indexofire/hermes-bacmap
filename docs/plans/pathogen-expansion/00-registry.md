# R0 · 病原注册表重构（pathogens.yaml 表驱动）

前置：无 · 后续：P1/P2/P3 与物种鉴定专项均依赖 · 估算：4 人日 · 验收核心：**加一个 stub 病原不修改任何 .smk 文件**

## 1. 问题

当前 4 病原的配置硬编码在 6+ 处，扩展到 15 病原不可维护：

| 现有硬编码 | 位置 | 内容 |
|---|---|---|
| `_GENE_TO_SPECIES` / `_SPECIES_PRIORITY` | `analysis/species_identifier.py` | marker → 物种 |
| `_GMLST_SCHEMES` | `rules/typing_amr.smk` | 经典 MLST scheme |
| `_AMRFINDER_ORGANISMS` | `rules/typing_amr.smk` | AMRFinderPlus organism |
| `_SPECIES_GROUPS` | `rules/snp.smk` | SNP 分组 + 参考基因组 |
| `_CGMLST_SCHEMES` / `_CGMLST_SPECIES_GROUPS` | `rules/cgmlst.smk` | cgMLST scheme + cohort 分组 |
| samples.tsv `species` 枚举 + skills 文档 | 散布 | 样本声明值域 |

## 2. 设计：`workflows/bacmap/config/pathogens.yaml`

每个病原一条记录，全部下游从该表驱动：

```yaml
pathogens:
  Salmonella:
    display_name: "沙门菌"
    marker_genes: [inva]                      # 物种鉴定（进 markers.fasta 注释管理）
    mlst_scheme: salmonella_2
    cgmlst_scheme: senterica_2                # null = 不启用
    cgmlst_thresholds: {outbreak: 10, clonal: 3, related: 50}   # null = UNDETERMINED
    amrfinder_organism: Salmonella
    serotype: {engine: sistr}                 # engine 名 → rule 分派；null = 无
    snp_group: salmonella                     # 多物种可共组（ecoli+Shigella）
    enabled: true
  "E.coli":
    display_name: "大肠埃希菌"
    marker_genes: [uida]
    mlst_scheme: ecoli_1
    cgmlst_scheme: ecoli_2
    cgmlst_thresholds: {outbreak: 5, related: 50, serotype_specific: {...}}
    amrfinder_organism: Escherichia
    serotype: {engine: ecoh}
    pathotype: dec                            # DEC 专属键，null = 无
    snp_group: ecoli
    enabled: true
  # ... P3 病原 enabled: false（默认关闭，显式启用）
```

SNP 分组的参考基因组独立成 `snp_groups:` 段（组名 → ref 路径 + 物种列表），消除 snp.smk 与 cgmlst.smk 里的重复分组字典。

## 3. 迁移清单（行为保持不变，纯重构）

| 文件 | 改动 |
|---|---|
| `workflows/bacmap/config/pathogens.yaml` | 新增（4 病原全量迁入） |
| `Snakefile` | 顶部加载注册表（`yaml.safe_load`），替换各 rule 文件的全局变量来源 |
| `rules/typing_amr.smk` / `snp.smk` / `cgmlst.smk` | `_GMLST_SCHEMES` 等 6 个字典改为从注册表查询函数取值（保留同名变量作薄封装，diff 最小化） |
| `analysis/species_identifier.py` | `_GENE_TO_SPECIES` 改为启动时从注册表构建（yaml 放包内只读副本或经 config.py 定位） |
| `scripts/vendor_cgmlst_schemes.py` | scheme 清单从注册表读取 |
| `scripts/build_cgmlst_reference.py` | 阈值/分组从注册表读取 |
| `tools/pipeline.py`（样本校验） | samples.tsv species 枚举校验从注册表取 |
| 物种鉴定专项（A-mini） | `taxa_filter.yaml` 由注册表 `marker_genes` 所属物种生成（协同点） |

## 4. 校验与工具

- `scripts/lint_pathogens.py`：注册表一致性检查（marker 基因在 markers.fasta 中存在、scheme 名在 gmlst 可用列表、amrfinder organism 在 `amrfinder -l` 列表、enabled=false 病原的样本出现在 samples.tsv 时报错）——CI 集成
- 注册表整体 sha256 记入 `database_signature`（三元证据链：加病原=签名变化，天然可追溯）

## 5. 测试计划

| 测试 | 内容 | 数量 |
|---|---|---|
| `test_pathogen_registry` | yaml 加载、必填字段校验、未知字段拒绝 | 5 |
| `test_registry_migration` | 4 病原重构前后：MLST scheme/分组/organism 映射逐一相等（黄金对照） | 8 |
| **stub 病原冒烟** | 注册表加 `Testomonas`（假 marker+scheme+group）→ snakemake --dry-run DAG 正确、species_identifier 可路由、**零 .smk 修改** | 3 |
| 全量回归 | 1415+ 测试全绿 | — |

## 6. 验收标准

1. stub 病原实验通过（R0 的核心承诺）
2. 4 病原 gold standard 12 株重跑结果与重构前字段级一致
3. `lint_pathogens.py` 入 CI，注册表任何不一致在 PR 阶段拦截
4. 全量测试无回归，mypy strict 零新增违规

## 7. 风险

| 风险 | 缓解 |
|---|---|
| Snakemake lambda 里查表失败（wildcard 物种不在表） | 查询函数带默认值 + lint 预检双保险 |
| yaml 引入新解析依赖 | PyYAML 已是运行时依赖（metadata_profiles 在用） |
| 重构期间行为漂移 | 黄金对照测试先行（TDD），4 病原全字段比对 |
