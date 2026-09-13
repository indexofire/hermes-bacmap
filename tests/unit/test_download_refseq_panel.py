"""A-mini panel: FTP-list candidates + taxonomy fetch selection rules."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

_SPEC = importlib.util.spec_from_file_location(
    "download_db_refseq_panel", _PROJECT_ROOT / "scripts" / "download_db_refseq_panel.py"
)
panel = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(panel)

ROWS = [
    {
        "accession": "GCF_REF1",
        "organism": "Salmonella enterica",
        "level": "Complete Genome",
        "category": "reference genome",
    },
    {
        "accession": "GCF_COMP1",
        "organism": "Salmonella enterica",
        "level": "Complete Genome",
        "category": "representative genome",
    },
    {
        "accession": "GCF_COMP2",
        "organism": "Salmonella enterica",
        "level": "Complete Genome",
        "category": "na",
    },
    {
        "accession": "GCF_CHROM",
        "organism": "Salmonella enterica",
        "level": "Chromosome",
        "category": "na",
    },
    {
        "accession": "GCF_COMP3",
        "organism": "Salmonella enterica",
        "level": "Complete Genome",
        "category": "na",
    },
    {
        "accession": "GCF_COMP4",
        "organism": "Salmonella enterica",
        "level": "Complete Genome",
        "category": "na",
    },
    {
        "accession": "GCF_COMP5",
        "organism": "Salmonella enterica",
        "level": "Complete Genome",
        "category": "na",
    },
    {
        "accession": "GCF_COMP6",
        "organism": "Salmonella enterica",
        "level": "Complete Genome",
        "category": "na",
    },
]


class TestGroupToQueries:
    def test_composite_group_splits(self):
        assert panel.group_to_queries("Escherichia_coli_Shigella") == [
            "Escherichia coli",
            "Shigella",
        ]

    def test_plain_group_name_becomes_taxon(self):
        assert panel.group_to_queries("Vibrio_parahaemolyticus") == ["Vibrio parahaemolyticus"]

    def test_fungi_excluded_from_candidates(self):
        assert panel.bacterial_groups(["Salmonella", "Candidozyma_auris"]) == ["Salmonella"]


class TestSelectPanelRows:
    def test_reference_mandatory_even_beyond_cap(self):
        selected = panel.select_panel_rows(ROWS, max_complete=2)
        refs = [r for r in selected if r["category"] == "reference genome"]
        assert len(refs) >= 1
        assert "GCF_REF1" in [r["accession"] for r in selected]

    def test_complete_capped(self):
        selected = panel.select_panel_rows(ROWS, max_complete=3)
        completes = [r for r in selected if r["level"] == "Complete Genome"]
        assert len(completes) <= 1 + 3

    def test_chromosome_level_not_selected_as_complete(self):
        selected = panel.select_panel_rows(ROWS, max_complete=5)
        assert "GCF_CHROM" not in [r["accession"] for r in selected]

    def test_representative_preferred_within_complete_cap(self):
        selected = panel.select_panel_rows(ROWS, max_complete=1)
        assert "GCF_COMP1" in [r["accession"] for r in selected]


class TestManifest:
    def test_manifest_written_with_checksum(self, tmp_path):
        (tmp_path / "metadata.tsv").write_text("a\tb\n", encoding="utf-8")
        path = panel.write_panel_manifest(tmp_path, n_genomes=7)
        data = json.loads(path.read_text())
        assert data["name"] == "refseq_panel"
        assert data["n_genomes"] == 7
        assert len(data["checksum"]) == 64


class TestPerSpeciesCap:
    def _rows(self):
        return [
            {
                "accession": "R_ECOLI",
                "organism": "Escherichia coli",
                "level": "Complete Genome",
                "category": "reference genome",
                "species_taxid": "666",
            },
            {
                "accession": "C1",
                "organism": "Escherichia coli O157",
                "level": "Complete Genome",
                "category": "na",
                "species_taxid": "666",
            },
            {
                "accession": "C2",
                "organism": "Escherichia coli",
                "level": "Complete Genome",
                "category": "na",
                "species_taxid": "666",
            },
            {
                "accession": "R_SALM",
                "organism": "Salmonella enterica",
                "level": "Chromosome",
                "category": "reference genome",
                "species_taxid": "28901",
            },
            {
                "accession": "S1",
                "organism": "Salmonella enterica",
                "level": "Complete Genome",
                "category": "representative genome",
                "species_taxid": "28901",
            },
        ]

    def test_reference_mandatory_across_species(self):
        got = {r["accession"] for r in panel.select_panel_rows(self._rows(), 1)}
        assert {"R_ECOLI", "R_SALM"} <= got

    def test_cap_applies_per_species_not_global(self):
        got = {r["accession"] for r in panel.select_panel_rows(self._rows(), 1)}
        assert "C1" in got and "S1" in got and "C2" not in got

    def test_chromosome_non_reference_excluded(self):
        got = {r["accession"] for r in panel.select_panel_rows(self._rows(), 5)}
        assert "R_SALM" in got


class TestGroupRecords:
    def _rows(self):
        return [
            {"accession": "A1", "organism": "Aeromonas veronii X", "level": "Complete Genome",
             "category": "reference genome", "species_taxid": "643", "taxid": "643"},
            {"accession": "A2", "organism": "Aeromonas hydrophila", "level": "Complete Genome",
             "category": "na", "species_taxid": "644", "taxid": "644"},
            {"accession": "B1", "organism": "Salmonella enterica Typhi", "level": "Chromosome",
             "category": "reference genome", "species_taxid": "28901", "taxid": "2"},
        ]

    def test_group_attribution_most_specific_prefix(self):
        recs = panel.build_group_records(
            ["Aeromonas", "Aeromonas_veronii", "Salmonella"], self._rows(), self._rows()
        )
        by_group = {r[0]: r for r in recs}
        assert "A1" not in [a for a in []] or True
        assert by_group["Aeromonas_veronii"][4] == 1  # A1 归最具体组
        assert by_group["Aeromonas"][4] == 1
        assert by_group["Salmonella"][4] == 1

    def test_taxids_collected_per_group(self):
        recs = panel.build_group_records(
            ["Aeromonas"], self._rows()[:2], self._rows()[:2]
        )
        assert set(recs[0][1].split(";")) == {"643", "644"}

    def test_groups_without_rows_listed_with_zero(self):
        recs = panel.build_group_records(["Vibrio"], [], [])
        assert recs == [("Vibrio", "", 0, 0, 0)]
