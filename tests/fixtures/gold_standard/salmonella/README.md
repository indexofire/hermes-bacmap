# Gold Standard 样本集

公卫验证用 Gold standard 样本集（project.md §12.3）。涵盖 **Salmonella + DEC + Shigella/EIEC** 三类病原。

## 样本清单（10 株）

| 株号 | 物种 | 血清型/Pathotype | SRA | 靶基因 | 状态 |
|---|---|---|---|---|---|
| SAM-TYP-001 | Salmonella | Typhimurium | SRR2407672 | invA+ | ✅ |
| SAM-TYP-002 | Salmonella | Typhimurium | SRR10252183 | invA+ | ✅ |
| SAM-ENT-003 | Salmonella | Newport | SRR5995933 | invA+ | ✅ |
| SAM-ENT-004 | Salmonella | Thompson | SRR10030182 | invA+ | ✅ |
| SAM-INF-005 | Salmonella | Infantis | SRR33422847 | invA+ | ✅ |
| SAM-NEW-006 | Salmonella | Newport | SRR4190235 | invA+ | ✅ |
| SAM-CTX-008 | S. Typhi | Typhi (CTX-M-15) | ERR2059823 | invA+ | ✅ |
| SAM-DEC-012 | E. coli O157 | STEC/aEPEC | DRR111461 | uidA+ ipaH- | ✅ |
| SAM-SHI-013 | Shigella flexneri | Shigella | ERR2287281 | uidA- ipaH+ | ✅ |
| SAM-EIEC-014 | EIEC | EIEC | SRR8186695 | uidA+ ipaH+ | ✅ |

## 物种鉴定靶基因

| 靶基因 | 目标物种 | 来源 | 长度 | 验证 |
|---|---|---|---|---|
| invA | Salmonella | M90846.1 | 2176 bp | ✅ 6/6 Sal 阳性 + 3/3 非 Sal 阴性 |
| uidA | E. coli/DEC | NC_000913.3 | 1190 bp | ✅ E.coli+DEC+EIEC 阳性, Sal+Shigella 阴性 |
| ipaH | Shigella/EIEC | NC_004337.2 | 1827 bp | ✅ Shigella+EIEC 阳性, Sal+DEC 阴性 |

## 文件清单

| 文件 | 用途 |
|---|---|
| `gold_standard.csv` | 人工编辑用，每行一株样本 |
| `data_dictionary.md` | 字段说明 + 数据源 + 验收标准 |
| `gold_standard.jsonl` | 程序读取用（pytest fixture 加载） |

## 样本分布（11 株，spec §12.3 V0.1）

| strain_id | BioSample | SRA | 类型 | 验证状态 |
|---|---|---|---|---|
| SAM-TYP-001 | SAMN03988352 | SRR2407672 | S. Typhimurium var. 5- (1,4,[5],12:i:-) ST34 | ✅ VERIFIED |
| SAM-TYP-002 | SAMN11787766 | PENDING | S. Typhimurium classic (4,5,12:i:1,2) ST19 | 🟡 BioSample confirmed (GenomeTrakr 2017 PT) |
| SAM-ENT-003 | SAMN07568553 | PENDING | S. Enteritidis ST11 | 🟡 BioSample confirmed (PulseNet 2017) |
| SAM-ENT-004 | SAMN12647593 | SRR10030182 | S. Enteritidis ST11 | ✅ VERIFIED (PulseNet 2019) |
| SAM-INF-005 | SAMN44339505 | SRR33422847 | S. Infantis ST32 + pESI megaplasmid | ✅ VERIFIED (carries blaCTX-M-65) |
| SAM-NEW-006 | SAMN05714009 | SRR4190235 | S. Newport ST45 | ✅ VERIFIED (PulseNet 2016) |
| SAM-PAN-008 | PENDING | PENDING | Pansusceptible (negative AMR control) | ⚠️ PENDING (query in CSV notes) |
| SAM-CTX-009 | PENDING | PENDING | ESBL with blaCTX-M-15 | ⚠️ PENDING (query in CSV notes) |
| SAM-CTX-010 | PENDING | PENDING | ESBL with blaCTX-M-14 | ⚠️ PENDING (query in CSV notes) |
| SAM-MCR-011 | PENDING | PENDING | Colistin-resistant with mcr-1 | ⚠️ PENDING (query in CSV notes) |
| SAM-ECO-012 | SAMN02929659 | SRR5226659 | *E. coli* ATCC 25922 (negative species control) | ✅ VERIFIED (CLSI QC strain) |

**Status**: 5/11 verified ✅ + 2/11 BioSample partial 🟡 + 4/11 pending ⚠️

### V0.2 expansion pool（保留，V0.1 未启用）

- **SAM-HEI-007** (S. Heidelberg ST15, SAMN01832089 / CFSAN002069) — 2013 multistate outbreak isolate, USA:WA chicken,
  PFGE JF6X01.0122. Closed genome GCF_000430085.2. PacBio + Illumina hybrid; verify Illumina-only run via SRS452294 before V0.2 inclusion.

## 数据源（按可信度）

| 来源 | 用途 | URL |
|---|---|---|
| NCBI Pathogen Detection | AMR/MLST/血清型已鉴定 | https://www.ncbi.nlm.nih.gov/pathogens/ |
| FDA GenomeTrakr | 食源性病原元数据 | https://www.ncbi.nlm.nih.gov/bioproject/?term=PRJNA186481 |
| EnteroBase | 完整 in silico 分析 | https://enterobase.warwick.ac.uk/ |
| PubMLST | MLST 权威 ST 编号 | https://pubmlst.org/organisms/salmonella-spp |
| PathogenWatch | 完整 in silico 分析 | https://pathogen.watch/ |

## 双源验证要求

每株的金标准答案必须来自 **≥2 个权威平台一致**：

| 字段 | 主源 | 复核源 |
|---|---|---|
| 血清型 | NCBI Pathogen Detection | EnteroBase in silico |
| MLST ST | PubMLST | EnteroBase / NCBI |
| AMR 基因 | AMRFinderPlus (NCBI) | ResFinder (CGE) / CARD |
| 毒力基因 | VFDB | Victors |
| 物种 | NCBI Taxonomy | GTDB |

## 验收标准

- [ ] 11 株全部有 SRA Run accession（Illumina PE100/PE150/PE250/PE300 均可）
- [ ] 11 株金标准答案双源一致（差异 > 5% 必须有解释）
- [ ] 11 株 FASTQ 已下载到 `data/samples/{strain_id}/fastq/`
- [ ] 11 株在 `gold_standard.csv` 中字段完整填写
- [ ] `gold_standard.jsonl` 与 `gold_standard.csv` 一致（脚本校验）
- [ ] pytest fixture `tests/conftest.py::gold_standard_set` 可加载

## 使用方式（Sprint 1+）

```python
# tests/conftest.py
@pytest.fixture(scope="session")
def gold_standard_set():
    """加载 Salmonella Gold standard 样本集（§12.3）。"""
    import csv
    from pathlib import Path
    csv_path = Path(__file__).parent / "fixtures/gold_standard/salmonella/gold_standard.csv"
    with csv_path.open() as f:
        return list(csv.DictReader(f))


# tests/integration/test_analytical_validation.py（Sprint 4）
def test_salmonella_serovar_accuracy(gold_standard_set, gos):
    """§12.3：血清型预测准确率 ≥ 95%。"""
    correct = 0
    for sample in gold_standard_set:
        if sample["species"] != "Salmonella enterica":
            continue  # 跳过阴性对照
        result = run_pipeline_and_get_serovar(sample)
        if result == sample["serovar"]:
            correct += 1
    accuracy = correct / sum(1 for s in gold_standard_set if s["species"] == "Salmonella enterica")
    assert accuracy >= 0.95
