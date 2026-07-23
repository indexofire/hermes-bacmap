# 菌株元数据 + 湿实验结果

> strain_metadata + lab_results + genome_objects 三表数据架构

---

## 概述

hermes-bacmap 使用三表架构管理菌株全生命周期数据：

| 表 | 定位 | 变更模式 | 每株行数 |
|---|---|---|---|
| **strain_metadata** | 背景信息（流行病学 + 送检） | 写一次，偶尔修正 | 1 |
| **lab_results** | 湿实验结果（药敏/血清/生化/PCR） | 可追加 | 0-50 |
| **genome_objects** | 生信分析结果（GOM） | 版本化，不可变 | 1+ |

三表通过 `strain_id` 1:1 或 1:N 关联，同一 SQLite 文件。

---

## strain_metadata（菌株背景信息）

### 核心列（27 个，建索引）

| 类别 | 字段 | 类型 | 说明 |
|---|---|---|---|
| **主键** | strain_id | TEXT | 菌株编号（与 GOM 关联） |
| **送检** | sample_id, submitting_lab, submit_date, receiver | TEXT/DATE | 送检登记信息 |
| **患者** | patient_id, patient_name, patient_age, patient_gender, patient_phone | TEXT/INT | 患者信息（脱敏） |
| **分离** | isolation_date, province, city, district, facility | TEXT/DATE | 分离时间地点 |
| **样品** | sample_source, sample_type, food_category, food_name, collection_date | TEXT/DATE | 样品来源分类 |
| **临床** | symptoms, onset_date, diagnosis, outcome, hospital | TEXT/DATE | 临床信息 |
| **暴发** | outbreak_id, cluster_note | TEXT | 暴发关联 |

### extra JSON 列（无限扩展）

非核心字段自动存入 JSON：

```python
svc.upsert("SAM-001", {
    "patient_name": "张三",        # → 核心列 patient_name
    "case_type": "暴发",           # → extra JSON
    "report_status": "已报",       # → extra JSON
    "custom_field": "...",         # → extra JSON
})
```

UPSERT 时 extra JSON **自动合并**（不覆盖已有扩展字段）。

### Python API

```python
from hermes_bacmap.services.strain_metadata import StrainMetadataService

svc = StrainMetadataService("data/hermes_bacmap.sqlite")

# 写入
svc.upsert("SAM-001", {"patient_name": "张三", "province": "北京"})

# 读取
meta = svc.get("SAM-001")
print(meta.patient_name, meta.province)

# 搜索（核心字段）
results = svc.search(province="北京", isolation_date_from="2024-01-01")

# 搜索（extra JSON）
results = svc.search(extra={"report_status": "已报"})

# TSV 导入
svc.import_tsv("samples_meta.tsv")

# 删除
svc.delete("SAM-001")
```

### TSV 导入格式

```tsv
strain_id	sample_id	patient_name	patient_age	province	isolation_date	sample_source	outbreak_id
SAM-TYP-001	SAM-TYP-001	张三	35	北京	2024-03-10	clinical	OB-2024-03
SAM-DEC-012	SAM-DEC-012	李四	28	上海	2024-04-18	clinical
```

---

## lab_results（湿实验结果）

### EAV 模式

每条实验结果一行，支持任意类型、任意数量的实验：

| category | 说明 | 示例 test_name | 一株几条 |
|---|---|---|---|
| ast | 药敏试验 | 氨苄西林, 环丙沙星, 头孢曲松 | 10-30 |
| serology | 血清学 | O抗原, H抗原 | 1-3 |
| biochemical | 生化试验 | 氧化酶, 靛基质, TSI | 5-15 |
| pcr | PCR | invA, stx1, stx2 | 1-5 |
| pfge | PFGE | XbaI | 1 |

### 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | UUID |
| strain_id | TEXT | 菌株编号 |
| category | TEXT | ast/serology/biochemical/pcr/pfge |
| test_name | TEXT | 检测项目名 |
| method | TEXT | broth_microdilution / disk_diffusion / antiserum |
| result | TEXT | 原始值（"16", "O4", "阳性"） |
| unit | TEXT | ug/mL, mm |
| interpretation | TEXT | S/I/R, positive/negative |
| standard | TEXT | CLSI M100-2024, GB 4789.4 |
| tested_date | TEXT | 检测日期 |
| tested_by | TEXT | 检测人 |
| lab | TEXT | 检测实验室 |
| extra | TEXT(JSON) | 扩展（抑菌圈直径, 质控菌株等） |

### Python API

```python
from hermes_bacmap.services.lab_results import LabResultService

svc = LabResultService("data/hermes_bacmap.sqlite")

# 单条录入
svc.add("SAM-001", "ast", "氨苄西林",
        result="16", unit="ug/mL", interpretation="R",
        method="broth_microdilution", standard="CLSI M100-2024")

# 批量录入（药敏面板）
svc.add_batch("SAM-001", "ast", [
    {"test_name": "氨苄西林", "result": "16", "interpretation": "R"},
    {"test_name": "环丙沙星", "result": "0.5", "interpretation": "S"},
    {"test_name": "头孢曲松", "result": "2", "interpretation": "I"},
])

# 查询
all_results = svc.get_by_strain("SAM-001")
ast_only = svc.get_by_strain("SAM-001", category="ast")
resistant = svc.search(category="ast", interpretation="R")

# 删除
svc.delete(result_id)
svc.delete_by_strain("SAM-001", category="ast")

# TSV 导入
svc.import_tsv("lab_results.tsv")
```

### TSV 导入格式

```tsv
strain_id	category	test_name	result	unit	interpretation	method	tested_date
SAM-TYP-001	ast	氨苄西林	16	ug/mL	R	broth_microdilution	2024-03-20
SAM-TYP-001	ast	环丙沙星	0.5	ug/mL	S	broth_microdilution	2024-03-20
SAM-TYP-001	serology	O抗原	O4		antiserum	2024-03-18
```

---

## 跨表查询

### 湿实验 vs 生信一致性比对

```sql
SELECT m.strain_id,
       m.patient_name, m.province,
       lr.result AS wet_serotype,
       json_extract(g.payload_json, '$.serotype.sistr') AS in_silco_serotype
FROM strain_metadata m
JOIN lab_results lr ON m.strain_id = lr.strain_id AND lr.category = 'serology'
JOIN genome_objects g ON m.strain_id = g.strain_id;
```

### 暴发调查

```sql
SELECT m.strain_id, m.patient_name, m.isolation_date,
       json_extract(g.payload_json, '$.serotype.sistr') AS serotype,
       json_extract(g.payload_json, '$.mlst') AS mlst
FROM strain_metadata m
JOIN genome_objects g ON m.strain_id = g.strain_id
WHERE m.outbreak_id = 'OB-2024-03'
ORDER BY m.isolation_date;
```

### 耐药监测

```sql
SELECT lr.test_name, lr.interpretation, COUNT(*) AS count
FROM lab_results lr
WHERE lr.category = 'ast' AND lr.interpretation = 'R'
GROUP BY lr.test_name
ORDER BY count DESC;
```

---

## Profile 模板（可扩展）

### 默认 Profile

`metadata_profiles/default.yaml` 定义 19 个核心字段（所有用户共享）。

### 自定义 Profile

```yaml
# metadata_profiles/cdc_china.yaml
name: cdc_china
extends: default

fields:
  - {name: case_type, type: enum, options: [散发, 暴发, 输入性], required: true}
  - {name: report_status, type: enum, options: [草稿, 待审, 已报, 退回]}
  - {name: sequencing_platform, type: enum, options: [MiSeq, NextSeq, NovaSeq]}
```

自定义字段自动存入 `extra` JSON，无需改表结构。

---

## 测试

24 个测试覆盖（`tests/unit/test_strain_metadata.py`）：

| 测试类 | 测试数 | 覆盖 |
|---|---|---|
| StrainMetadataCRUD | 5 | upsert/get/delete |
| StrainMetadataExtra | 3 | JSON 存储/合并/分离 |
| StrainMetadataSearch | 4 | 省/暴发/日期/extra |
| StrainMetadataImport | 1 | TSV 导入 |
| LabResultCRUD | 5 | add/batch/delete |
| LabResultSearch | 3 | category/interpretation/strain_ids |
| LabResultExtra | 1 | 扩展字段 |
| LabResultImport | 1 | TSV 导入 |
| Integration | 1 | 三表 JOIN |
