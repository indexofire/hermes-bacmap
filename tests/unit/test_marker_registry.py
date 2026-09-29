"""Unit tests for marker registration (services/marker_registry.py).

Additive, atomic updates to marker_rules.yaml (+ optional sequence append to
markers fasta); idempotent re-registration; validation of species/gene
names; backup of previous state.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.services.marker_registry import register_marker  # noqa: E402


def _rules(tmp_path: Path) -> Path:
    rules = tmp_path / "marker_rules.yaml"
    rules.write_text(
        """rules:
- species: Salmonella
  genes:
  - inva
  min_hits: 1
  min_identity: 90
- species: Vibrio_cholerae
  genes:
  - ompw
  - ctxa
  min_hits: 1
  min_identity: 90
""",
        encoding="utf-8",
    )
    return rules


class TestRegisterMarker:
    def test_appends_gene_to_existing_species_rule(self, tmp_path):
        rules = _rules(tmp_path)

        result = register_marker("Salmonella", "outbreak_marker", rules_path=rules)

        assert result["action"] == "appended"
        assert result["species"] == "Salmonella"
        assert "outbreak_marker" in result["genes"]

        content = rules.read_text()
        assert "- outbreak_marker" in content
        assert "inva" in content

    def test_creates_new_species_rule(self, tmp_path):
        rules = _rules(tmp_path)

        result = register_marker(
            "Yersinia_enterocolitica", "ail", rules_path=rules, min_identity=95
        )

        assert result["action"] == "created"
        content = rules.read_text()
        assert "Yersinia_enterocolitica" in content
        assert "min_identity: 95" in content

    def test_idempotent_when_gene_exists(self, tmp_path):
        rules = _rules(tmp_path)

        result = register_marker("Vibrio_cholerae", "ompw", rules_path=rules)

        assert result["action"] == "already_present"

    def test_creates_backup(self, tmp_path):
        rules = _rules(tmp_path)
        before = rules.read_text()

        register_marker("Salmonella", "newgene", rules_path=rules)

        backup = tmp_path / "marker_rules.yaml.bak"
        assert backup.exists()
        assert backup.read_text() == before

    def test_normalizes_species_and_gene(self, tmp_path):
        rules = _rules(tmp_path)

        result = register_marker("salmonella enterica", "INV-B", rules_path=rules)

        assert result["species"] == "Salmonella_enterica"
        assert "inv-b" in result["genes"]

    def test_rejects_invalid_species_name(self, tmp_path):
        rules = _rules(tmp_path)

        with pytest.raises(ValueError, match="species"):
            register_marker("Salmonella; DROP TABLE", "x", rules_path=rules)

    def test_appends_fasta_sequence_when_given(self, tmp_path):
        rules = _rules(tmp_path)
        fasta = tmp_path / "markers_v2.fasta"
        fasta.write_text(">existing\nATGC\n")
        seq = tmp_path / "new_marker.fa"
        seq.write_text(">outbreak_marker desc here\nATGGCCTTAA\n")

        result = register_marker(
            "Salmonella",
            "outbreak_marker",
            rules_path=rules,
            markers_fasta=fasta,
            sequence_fasta=seq,
        )

        content = fasta.read_text()
        assert ">outbreak_marker" in content
        assert "ATGGCCTTAA" in content
        assert result["fasta_appended"] is True

    def test_fasta_append_deduplicates(self, tmp_path):
        rules = _rules(tmp_path)
        fasta = tmp_path / "markers_v2.fasta"
        fasta.write_text(">outbreak_marker\nATGGCCTTAA\n")
        seq = tmp_path / "new_marker.fa"
        seq.write_text(">outbreak_marker\nATGGCCTTAA\n")

        result = register_marker(
            "Salmonella",
            "outbreak_marker",
            rules_path=rules,
            markers_fasta=fasta,
            sequence_fasta=seq,
        )

        assert result["fasta_appended"] is False
        assert fasta.read_text().count(">outbreak_marker") == 1
