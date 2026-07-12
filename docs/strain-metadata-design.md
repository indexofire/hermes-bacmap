# 菌株背景信息数据方案

> **定位**: 菌株元数据（流行病学 + 送检 + 溯源），固定写入，极少修改
> **与 GOM 关系**: 同一 SQLite 文件，通过 strain_id 1:1 关联

---

## 设计原则

| 维度 | 菌株元数据 (新) | 分析结果 (GOM 现有) |
|---|---|---|
| **变更模式** | 写入后固定不变（偶尔修正） | 版本化（每次重分析新建版本） |
| **数据来源** | 人工录入 / LIMS 导入 | Snakemake 管线自动产出 |
| **写入时机** | 送检登记时（分析前） | 分析完成后（ingest_results.py） |
| **完整性** | 可缺字段（非每株都有患者信息） | 必须完整（管线产出） |
| **Schema** | 固定列 + JSON 扩展 | 全 JSON payload |

## 表设计

```sql
CREATE TABLE IF NOT EXISTS strain_metadata (
    strain_id       TEXT PRIMARY KEY,
    
    -- 送检信息
    sample_id       TEXT NOT NULL,
    submitting_lab  TEXT,
    submit_date     TEXT,
    receiver        TEXT,
    
    -- 患者信息（脱敏）
    patient_id      TEXT,
    patient_name    TEXT,
    patient_age     INTEGER,
    patient_gender  TEXT,
    patient_phone   TEXT,
    
    -- 分离信息
    isolation_date  TEXT,
    province        TEXT,
    city            TEXT,
    district        TEXT,
    facility        TEXT,
    
    -- 样品信息
    sample_source   TEXT,
    sample_type     TEXT,
    food_category   TEXT,
    food_name       TEXT,
    collection_date TEXT,
    
    -- 临床信息
    symptoms        TEXT,
    onset_date      TEXT,
    diagnosis       TEXT,
    outcome         TEXT,
    hospital        TEXT,
    
    -- 暴发关联
    outbreak_id     TEXT,
    cluster_note    TEXT,
    
    -- 扩展字段
    extra           TEXT,
    
    -- 审计
    created_at      TEXT NOT NULL,
    updated_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_meta_sample_id ON strain_metadata(sample_id);
CREATE INDEX IF NOT EXISTS idx_meta_outbreak ON strain_metadata(outbreak_id);
CREATE INDEX IF NOT EXISTS idx_meta_isolation_date ON strain_metadata(isolation_date);
CREATE INDEX IF NOT EXISTS idx_meta_province ON strain_metadata(province);
```

## 数据流

```
samples_meta.tsv (扩展 TSV)
    │
    │ python scripts/import_meta.py --tsv samples_meta.tsv
    ▼
strain_metadata 表 (SQLite)
    │
    │ strain_id = SAM-TYP-001
    │
    ├── JOIN → genome_objects (分析结果)
    ├── JOIN → events (生命周期)
    └── JOIN → file_artifacts (文件产物)
```

## samples_meta.tsv 格式

扩展现有 samples.tsv，增加流行病学列。未知的列留空：

```tsv
strain_id	sample_id	species	R1	R2	submitting_lab	submit_date	patient_id	patient_name	patient_age	patient_gender	isolation_date	province	city	district	sample_source	sample_type	food_category	outbreak_id
SAM-TYP-001	SAM-TYP-001	Salmonella	tests/.../R1.fq.gz	tests/.../R2.fq.gz	北京市疾控	2024-03-15	P001	张三	35	M	2024-03-10	北京	北京市	海淀区	clinical	stool		SAL-2024-03
SAM-DEC-012	SAM-DEC-012	E.coli	tests/.../R1.fq.gz	tests/.../R2.fq.gz	上海市疾控	2024-04-20	P045	李四	28	F	2024-04-18	上海	上海市	浦东新区	clinical	stool	肉类	
```

也可以用 JSON 格式批量导入：

```json
{
  "strain_id": "SAM-TYP-001",
  "sample_id": "SAM-TYP-001",
  "patient_name": "张三",
  "patient_age": 35,
  "patient_gender": "M",
  "isolation_date": "2024-03-10",
  "province": "北京",
  "sample_source": "clinical",
  "outbreak_id": "SAL-2024-03"
}
```

## Python API

```python
from hermes_bacmap.strain_metadata import StrainMetadataService

# 写入
svc = StrainMetadataService("data/hermes_bacmap.sqlite")
svc.upsert("SAM-TYP-001", {
    "patient_name": "张三",
    "patient_age": 35,
    "isolation_date": "2024-03-10",
    "province": "北京",
})

# 查询
meta = svc.get("SAM-TYP-001")
print(meta.patient_name, meta.isolation_date)

# 按条件搜索
results = svc.search(province="北京", sample_source="clinical")

# 与 GOM 联合查询
combined = svc.join_analysis("SAM-TYP-001")
# → {patient: {...}, analysis: {species: Salmonella, mlst: ST19, ...}}
```

## Hermes 工具扩展

`bio_search_samples` 增强为跨表搜索：

```
用户: "北京地区 2024 年 3 月分离的沙门菌有哪些？"

LLM 调用 bio_search_samples(query="北京 Salmonella 2024-03")
  → strain_metadata: WHERE province='北京' AND isolation_date LIKE '2024-03%'
  → genome_objects: WHERE organism='Salmonella'
  → JOIN 返回: 样本列表 + 分析结果
```

## 实现计划

| 步骤 | 内容 | 工作量 |
|---|---|---|
| 1 | `strain_metadata.py` — StrainMetadataService 类 + StrainMeta dataclass | 中 |
| 2 | `import_meta.py` — TSV/JSON 导入脚本 | 小 |
| 3 | samples.tsv 向后兼容（新增列可选） | 小 |
| 4 | `bio_search_samples` 扩展为跨表 JOIN | 中 |
| 5 | Web UI 增加元数据列 | 小 |
| 6 | 文档更新 | 小 |
