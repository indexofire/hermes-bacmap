"""Tests for utils.py — parse_mlst, parse_abricate_tsv, read_json_file."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.utils import parse_mlst, parse_abricate_tsv, read_json_file  # noqa: E402


class TestParseMlst:
    def test_normal(self):
        tsv = "FILE\tSCHEME\tST\taroC\tdnaN\ncontigs\tsalmonella_2\t19\t10\t7"
        r = parse_mlst(tsv)
        assert r["st"] == "19"
        assert r["alleles"]["aroc"] == "10"

    def test_no_st_column(self):
        tsv = "FILE\tSCHEME\taroC\tdnaN\ncontigs\tsalmonella_2\t10\t7"
        r = parse_mlst(tsv)
        assert r["st"] == "N/A"

    def test_empty_st_value(self):
        tsv = "FILE\tSCHEME\tST\taroC\ncontigs\tsalmonella_2\t\t10"
        r = parse_mlst(tsv)
        assert r["st"] in ("", "N/A")

    def test_st_dash(self):
        tsv = "FILE\tSCHEME\tST\taroC\ncontigs\tsalmonella_2\t-\t10"
        r = parse_mlst(tsv)
        assert r["st"] in ("-", "N/A", "")

    def test_empty_input(self):
        assert parse_mlst("")["st"] == "N/A"
        assert parse_mlst("N/A")["st"] == "N/A"

    def test_header_only(self):
        r = parse_mlst("FILE\tSCHEME\tST")
        assert r["st"] == "N/A"


class TestParseAbricateTsv:
    def test_normal(self):
        tsv = "#FILE\tGENE\tCOVERAGE\nfile1\tblaCTX-M\t100/100"
        r = parse_abricate_tsv(tsv)
        assert len(r) == 1
        assert r[0]["GENE"] == "blaCTX-M"

    def test_short_row_not_dropped(self):
        tsv = "#FILE\tGENE\tCOVERAGE\tPRODUCT\nfile1\tblaCTX-M\t100/100"
        r = parse_abricate_tsv(tsv)
        assert len(r) == 1
        assert r[0]["GENE"] == "blaCTX-M"
        assert r[0].get("PRODUCT") == "" or r[0].get("PRODUCT") is None

    def test_hash_prefix_normalized(self):
        tsv = "#FILE\tGENE\nfile1\tblaCTX-M"
        r = parse_abricate_tsv(tsv)
        assert len(r) == 1
        assert "FILE" in r[0] or "#FILE" in r[0]

    def test_empty(self):
        assert parse_abricate_tsv("") == []
        assert parse_abricate_tsv("HEADER_ONLY") == []


class TestReadJsonFile:
    def test_normal(self, tmp_path):
        p = tmp_path / "test.json"
        p.write_text('{"key": "value"}')
        assert read_json_file(p) == {"key": "value"}

    def test_missing(self, tmp_path):
        assert read_json_file(tmp_path / "nonexistent.json") is None

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.json"
        p.write_text("")
        assert read_json_file(p) is None

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{invalid")
        assert read_json_file(p) is None

    def test_permission_denied(self, tmp_path):
        p = tmp_path / "noperm.json"
        p.write_text('{"key": "value"}')
        p.chmod(0o000)
        try:
            result = read_json_file(p)
            assert result is None
        finally:
            p.chmod(0o644)
