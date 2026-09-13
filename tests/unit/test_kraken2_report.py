"""Kraken2 prefilter report parsing (species-id plan D)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

_SPEC = importlib.util.spec_from_file_location(
    "kraken2_report", _PROJECT_ROOT / "workflows/bacmap/scripts/kraken2_report.py"
)
kraken2_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(kraken2_report)

KRAKEN2_REPORT = """\
  1.50  1500  30  R  1  root
 97.20 97200 1944  S  2  Salmonella enterica
  0.80   800   16  S  9606 Homo sapiens
"""

BRACKEN_TSV = (
    "name\ttaxonomy_id\ttaxonomy_lv\tkraken_assigned_reads\tadded_reads\t"
    "new_est_reads\tfraction_total_reads\n"
    "Salmonella enterica\t2\tS\t97200\t300\t97500\t0.9750\n"
    "Homo sapiens\t9606\tS\t800\t0\t800\t0.0080\n"
)


class TestParseReport:
    def test_species_percentages(self):
        parsed = kraken2_report.parse_kraken2_report(KRAKEN2_REPORT)
        assert parsed["Salmonella enterica"] == 97.20
        assert parsed["Homo sapiens"] == 0.80


class TestBuildResult:
    def test_on_target_high(self):
        res = kraken2_report.build_result(
            KRAKEN2_REPORT, BRACKEN_TSV, declared_species="Salmonella"
        )
        assert res["method"] == "kraken2"
        assert res["result"]["species"] == "Salmonella enterica"
        assert res["result"]["confidence"] == "high"
        assert res["result"]["host_reads_removed_pct"] == 0.80
        assert res["result"]["flags"] == []

    def test_off_target_flagged(self):
        report = (
            KRAKEN2_REPORT.replace("97.20", "42.0").replace("97200", "42000").replace("1944", "840")
        )
        bracken = BRACKEN_TSV.replace("0.9750", "0.4200")
        res = kraken2_report.build_result(report, bracken, declared_species="Salmonella")
        assert res["result"]["confidence"] == "low"
        assert "off_target_species" in res["result"]["flags"]

    def test_moderate_zone(self):
        report = (
            KRAKEN2_REPORT.replace("97.20", "70.0")
            .replace("97200", "70000")
            .replace("1944", "1400")
        )
        bracken = BRACKEN_TSV.replace("0.9750", "0.7000")
        res = kraken2_report.build_result(report, bracken, declared_species="Salmonella")
        assert res["result"]["confidence"] == "medium"

    def test_high_host_content_flag(self):
        report = KRAKEN2_REPORT.replace("0.80", "15.0").replace("800", "15000").replace("16", "300")
        res = kraken2_report.build_result(report, BRACKEN_TSV, declared_species="Salmonella")
        assert "high_host_content" in res["result"]["flags"]
