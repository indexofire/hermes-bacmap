# 可扩展 Metadata 方案

## 核心思路：固定核心列 + JSON 扩展列 + Profile 模板

```
strain_metadata 表
├── 核心列 (20 个，所有用户共享，建索引)
│   strain_id, sample_id, patient_*, isolation_*, sample_*, ...
│
├── extra (JSON，任意扩展字段)
│   {"case_type": "sporadic", "report_status": "draft", ...}
│
└── Profile 模板 (YAML，定义不同场景的字段)
    metadata_profiles/
    ├── default.yaml        # 核心 + 通用扩展
    ├── cdc_china.yaml      # 中国疾控监测
    ├── food_safety.yaml    # 食品安全专项
    └── custom.yaml         # 用户自定义
```

## 三层架构

### Layer 1: 核心列（代码定义，编译期固定）

所有用户都有，建索引，支持 SQL WHERE 查询：

```sql
strain_id, sample_id, submitting_lab, submit_date,
patient_id, patient_name, patient_age, patient_gender,
isolation_date, province, city, district, facility,
sample_source, sample_type, food_category, food_name,
outbreak_id, diagnosis, outcome
```

**不可增减**——修改需要版本发布。

### Layer 2: extra JSON 列（运行时扩展，无限制）

```sql
extra TEXT  -- JSON blob
```

任何字段直接写入，无需改表：

```python
svc.upsert("SAM-TYP-001", {
    "patient_name": "张三",           # → 核心列
    "case_type": "sporadic",          # → extra JSON
    "report_status": "draft",         # → extra JSON
    "antibiotic_history": "环丙沙星",  # → extra JSON
    "custom_field_123": "...",        # → extra JSON
})
```

**无限制扩展**——不修改表结构、不需要迁移。

### Layer 3: Profile 模板（YAML，验证 + UI + 文档）

```yaml
# metadata_profiles/cdc_china.yaml
name: cdc_china
description: 中国食源性疾病主动监测
extends: default

fields:
  - name: case_type
    type: enum
    required: true
    options: [散发, 暴发, 输入性]
    
  - name: report_status
    type: enum
    default: 草稿
    options: [草稿, 待审, 已报, 退回]
    
  - name: notification_card_no
    type: string
    pattern: "^CFX-\\d{4}-\\d{6}$"
    
  - name: antibiotic_before_culture
    type: boolean
    
  - name: hospitalization_days
    type: integer
    min: 0
    max: 365
```

Profile 只定义**验证规则和 UI 展示**，不改变存储——所有自定义字段都进 `extra` JSON。

## 数据流

```
用户录入 / TSV 导入 / API 调用
        │
        ▼
┌─────────────────────┐
│  Profile 验证        │
│  (cdc_china.yaml)   │
│                     │
│  核心字段 → 核心列    │
│  扩展字段 → extra JSON│
│  缺失必填 → 报错      │
│  类型不匹配 → 报错    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────────────┐
│ strain_metadata 表               │
│                                 │
│ strain_id = "SAM-TYP-001"       │
│ patient_name = "张三"            │
│ province = "北京"                │
│ extra = {                       │
│   "case_type": "暴发",           │
│   "report_status": "已报",       │
│   "notification_card_no": "..."  │
│ }                               │
└─────────────────────────────────┘
```

## 查询

### 核心字段查询（SQL WHERE，索引加速）

```sql
SELECT * FROM strain_metadata
WHERE province = '北京' AND isolation_date >= '2024-01-01';
```

### 扩展字段查询（JSON 函数）

```sql
-- SQLite JSON 查询
SELECT strain_id, json_extract(extra, '$.case_type') as case_type
FROM strain_metadata
WHERE json_extract(extra, '$.report_status') = '已报';

-- Python API
svc.search(extra={"report_status": "已报"})
```

### 跨表联合（GOM + Metadata）

```sql
SELECT m.strain_id, m.patient_name, m.province,
       g.payload_json
FROM strain_metadata m
JOIN genome_objects g ON m.strain_id = g.strain_id
WHERE m.province = '北京'
  AND json_extract(g.payload_json, '$.species_verdict') = 'Salmonella'
  AND m.isolation_date >= '2024-01-01';
```

## 用户自定义 Profile

新建用户只需创建一个 YAML 文件：

```yaml
# metadata_profiles/my_lab.yaml
name: my_lab
description: 我实验室的自定义字段
extends: default

fields:
  - name: our_project_id
    type: string
    required: true
    
  - name: sequencing_platform
    type: enum
    options: [MiSeq, NextSeq, NovaSeq, GridION]
    
  - name: contamination_check
    type: enum
    options: [pass, fail, retest]
    
  - name: assigned_to
    type: string
```

```bash
# 使用自定义 profile
python scripts/import_meta.py --tsv my_samples.tsv --profile my_lab
```

无需改代码、无需改表结构、无需重新部署。

## Hermes 集成

```
用户: "帮我录入 SAM-NEW-015 的背景信息"
LLM: → 加载当前 profile (cdc_china.yaml)
    → 生成录入提示（列出必填字段）
    → 用户回答
    → 验证 + 写入 strain_metadata

用户: "统计今年北京市各血清型的分布"
LLM: → SQL JOIN strain_metadata + genome_objects
    → GROUP BY serotype
    → 返回统计表
```

## 默认 Profile (default.yaml)

```yaml
name: default
description: 核心字段（所有用户共享）
core_only: true

fields:
  # 送检
  - {name: submitting_lab, type: string}
  - {name: submit_date, type: date}
  # 患者
  - {name: patient_id, type: string}
  - {name: patient_name, type: string}
  - {name: patient_age, type: integer, min: 0, max: 150}
  - {name: patient_gender, type: enum, options: [M, F]}
  # 分离
  - {name: isolation_date, type: date}
  - {name: province, type: string}
  - {name: city, type: string}
  - {name: district, type: string}
  - {name: facility, type: string}
  # 样品
  - {name: sample_source, type: enum, options: [临床, 食品, 环境, 其他]}
  - {name: sample_type, type: string}
  - {name: food_category, type: string}
  # 暴发
  - {name: outbreak_id, type: string}
```
