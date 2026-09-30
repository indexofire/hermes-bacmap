"""通用分型规则引擎 — 基因组合 → 型别（数据驱动，无逐病原硬编码）。

规则文件（YAML）与 gapit DB 目录同置（data/reference/typing/<scheme>/
typing_rules.yaml），实现"数据库内聚"架构：新增型别判读只需添加规则文件，
无需修改代码。未来 gapit 原生支持时可直接读取同一格式。

规则文件结构见各 scheme 目录下的 typing_rules.yaml。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..analysis.gene_scanner import scan

_TYPING_DIR = Path(__file__).resolve().parents[3] / "data/reference/typing"


@dataclass
class TypingResult:
    scheme: str = ""
    species: str = ""
    call: dict[str, Any] = field(default_factory=dict)
    confidence: str = "low"
    detected_genes: list[dict[str, Any]] = field(default_factory=list)
    interpretation: str = ""
    rule_id: str = ""
    database_version: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_type": "typing",
            "scheme": self.scheme,
            "species": self.species,
            "method": "gene_combination_rules",
            "database": {"name": self.scheme, "version": self.database_version},
            "result": {**self.call, "confidence": self.confidence},
            "detected_genes": self.detected_genes,
            "interpretation": self.interpretation,
            "rule_id": self.rule_id,
        }


def list_schemes() -> list[str]:
    return sorted(p.parent.name for p in _TYPING_DIR.glob("*/typing_rules.yaml"))


def type_by_rules(contigs_fasta: str | Path, scheme: str) -> TypingResult:
    rules_path = _TYPING_DIR / scheme / "typing_rules.yaml"
    if not rules_path.is_file():
        raise ValueError(f"typing scheme not found: {scheme} (expected {rules_path})")

    cfg = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    min_id = float(cfg.get("min_identity", 85))
    min_cov = float(cfg.get("min_coverage", 30))
    markers = set(str(k).lower() for k in (cfg.get("markers") or {}))

    scan_result = scan(
        contigs_fasta,
        db_name=cfg.get("database", "markers_v2"),
        min_identity=min_id,
        min_coverage=min_cov,
    )

    gene_hits: dict[str, dict[str, Any]] = {}
    for hit in scan_result.genes:
        gene = hit.gene.lower()
        if gene in markers and (
            gene not in gene_hits or hit.identity > gene_hits[gene]["identity"]
        ):
            gene_hits[gene] = {
                "gene": hit.gene,
                "identity": hit.identity,
                "coverage": hit.coverage,
            }

    result = TypingResult(
        scheme=cfg.get("scheme", scheme),
        species=cfg.get("species", ""),
        database_version=str(rules_path.stat().st_mtime_ns)[:8],
    )
    result.detected_genes = list(gene_hits.values())

    for rule in cfg.get("rules") or []:
        when = rule.get("when") or {}
        if _matches(when, gene_hits):
            result.rule_id = str(rule.get("id", ""))
            result.call = dict(rule.get("call") or {})
            result.confidence = str(result.call.pop("confidence", "low"))
            result.interpretation = str(rule.get("interpretation", ""))
            return result

    result.interpretation = "no rule matched"
    return result


def _matches(when: dict[str, Any], hits: dict[str, dict[str, Any]]) -> bool:
    for gene, expected in when.items():
        present = gene.lower() in hits
        if expected == "+" and not present:
            return False
        if expected == "-" and present:
            return False
    return True
