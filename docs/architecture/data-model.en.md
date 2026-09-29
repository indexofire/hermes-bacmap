# Strain Metadata + Wet-Lab Results

> Three-table data architecture: strain_metadata + lab_results + genome_objects

---

## Overview

hermes-bacmap uses a three-table architecture to manage full-lifecycle strain data:

| Table | Role | Change pattern | Rows per strain |
|---|---|---|---|
| **strain_metadata** | Background info (epidemiology + submission) | Write once, occasional corrections | 1 |
| **lab_results** | Wet-lab results (AST/serology/biochemical/PCR) | Appendable | 0-50 |
| **genome_objects** | Bioinformatics results (GOM) | Versioned, immutable | 1+ |

The three tables are linked by `strain_id` in 1:1 or 1:N relationships, all within one SQLite file.

---

## strain_metadata (strain background info)

### Core columns (27, indexed)

| Category | Fields | Type | Description |
|---|---|---|---|
| **Primary key** | strain_id | TEXT | Strain ID (linked to GOM) |
| **Submission** | sample_id, submitting_lab, submit_date, receiver | TEXT/DATE | Submission registration info |
| **Patient** | patient_id, patient_name, patient_age, patient_gender, patient_phone | TEXT/INT | Patient info (de-identified) |
| **Isolation** | isolation_date, province, city, district, facility | TEXT/DATE | Time and place of isolation |
| **Sample** | sample_source, sample_type, food_category, food_name, collection_date | TEXT/DATE | Sample source classification |
| **Clinical** | symptoms, onset_date, diagnosis, outcome, hospital | TEXT/DATE | Clinical information |
| **Outbreak** | outbreak_id, cluster_note | TEXT | Outbreak association |

### extra JSON column (unlimited extension)

Non-core fields are automatically stored as JSON:

```python
svc.upsert("SAM-001", {
    "patient_name": "张三",        # → 核心列 patient_name
    "case_type": "暴发",           # → extra JSON
    "report_status": "已报",       # → extra JSON
    "custom_field": "...",         # → extra JSON
})
```

On UPSERT, the extra JSON is **merged automatically** (existing extension fields are not overwritten).

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

### TSV import format

```tsv
strain_id	sample_id	patient_name	patient_age	province	isolation_date	sample_source	outbreak_id
SAM-TYP-001	SAM-TYP-001	张三	35	北京	2024-03-10	clinical	OB-2024-03
SAM-DEC-012	SAM-DEC-012	李四	28	上海	2024-04-18	clinical
```

---

## lab_results (wet-lab results)

### EAV pattern

One row per test result, supporting any type and any number of tests:

| category | Description | Example test_name | Rows per strain |
|---|---|---|---|
| ast | Antimicrobial susceptibility testing | 氨苄西林, 环丙沙星, 头孢曲松 | 10-30 |
| serology | Serology | O抗原, H抗原 | 1-3 |
| biochemical | Biochemical tests | 氧化酶, 靛基质, TSI | 5-15 |
| pcr | PCR | invA, stx1, stx2 | 1-5 |
| pfge | PFGE | XbaI | 1 |

### Fields

| Field | Type | Description |
|---|---|---|
| id | TEXT PK | UUID |
| strain_id | TEXT | Strain ID |
| category | TEXT | ast/serology/biochemical/pcr/pfge |
| test_name | TEXT | Test name |
| method | TEXT | broth_microdilution / disk_diffusion / antiserum |
| result | TEXT | Raw value ("16", "O4", "阳性") |
| unit | TEXT | ug/mL, mm |
| interpretation | TEXT | S/I/R, positive/negative |
| standard | TEXT | CLSI M100-2024, GB 4789.4 |
| tested_date | TEXT | Test date |
| tested_by | TEXT | Tester |
| lab | TEXT | Testing laboratory |
| extra | TEXT(JSON) | Extensions (inhibition zone diameter, QC strains, etc.) |

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

### TSV import format

```tsv
strain_id	category	test_name	result	unit	interpretation	method	tested_date
SAM-TYP-001	ast	氨苄西林	16	ug/mL	R	broth_microdilution	2024-03-20
SAM-TYP-001	ast	环丙沙星	0.5	ug/mL	S	broth_microdilution	2024-03-20
SAM-TYP-001	serology	O抗原	O4		antiserum	2024-03-18
```

---

## Cross-table queries

### Wet-lab vs bioinformatics consistency comparison

```sql
SELECT m.strain_id,
       m.patient_name, m.province,
       lr.result AS wet_serotype,
       json_extract(g.payload_json, '$.serotype.sistr') AS in_silco_serotype
FROM strain_metadata m
JOIN lab_results lr ON m.strain_id = lr.strain_id AND lr.category = 'serology'
JOIN genome_objects g ON m.strain_id = g.strain_id;
```

### Outbreak investigation

```sql
SELECT m.strain_id, m.patient_name, m.isolation_date,
       json_extract(g.payload_json, '$.serotype.sistr') AS serotype,
       json_extract(g.payload_json, '$.mlst') AS mlst
FROM strain_metadata m
JOIN genome_objects g ON m.strain_id = g.strain_id
WHERE m.outbreak_id = 'OB-2024-03'
ORDER BY m.isolation_date;
```

### Resistance surveillance

```sql
SELECT lr.test_name, lr.interpretation, COUNT(*) AS count
FROM lab_results lr
WHERE lr.category = 'ast' AND lr.interpretation = 'R'
GROUP BY lr.test_name
ORDER BY count DESC;
```

---

## Profile templates (extensible)

### Default profile

`metadata_profiles/default.yaml` defines 19 core fields (shared by all users).

### Custom profiles

```yaml
# metadata_profiles/cdc_china.yaml
name: cdc_china
extends: default

fields:
  - {name: case_type, type: enum, options: [散发, 暴发, 输入性], required: true}
  - {name: report_status, type: enum, options: [草稿, 待审, 已报, 退回]}
  - {name: sequencing_platform, type: enum, options: [MiSeq, NextSeq, NovaSeq]}
```

Custom fields are automatically stored in the `extra` JSON — no schema changes required.

---

## Tests

24 tests provide coverage (`tests/unit/test_strain_metadata.py`):

| Test class | Tests | Coverage |
|---|---|---|
| StrainMetadataCRUD | 5 | upsert/get/delete |
| StrainMetadataExtra | 3 | JSON storage/merge/separation |
| StrainMetadataSearch | 4 | province/outbreak/date/extra |
| StrainMetadataImport | 1 | TSV import |
| LabResultCRUD | 5 | add/batch/delete |
| LabResultSearch | 3 | category/interpretation/strain_ids |
| LabResultExtra | 1 | Extension fields |
| LabResultImport | 1 | TSV import |
| Integration | 1 | Three-table JOIN |
