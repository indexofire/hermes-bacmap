"""Validation genome downloader (NCBI Datasets, species-id validation)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

_SPEC = importlib.util.spec_from_file_location(
    "download_validation_genomes",
    _PROJECT_ROOT / "scripts" / "download_validation_genomes.py",
)
dvg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dvg)

SUMMARY_JSON_LINES = "\n".join(
    json.dumps(item)
    for item in [
        {
            "accession": "GCF_000006945.2",
            "organism": {"organism_name": "Salmonella enterica"},
            "assembly_info": {
                "assembly_level": "Complete Genome",
                "refseq_category": "representative genome",
            },
        },
        {
            "accession": "GCF_000195995.1",
            "organism": {"organism_name": "Salmonella enterica"},
            "assembly_info": {
                "assembly_level": "Contig",
                "refseq_category": "representative genome",
            },
        },
        {
            "accession": "GCF_999999999.9",
            "organism": {"organism_name": "Salmonella enterica"},
            "assembly_info": {
                "assembly_level": "Chromosome",
                "refseq_category": "na",
            },
        },
    ]
)


class TestPathogenConfig:
    def test_targets_cover_current_four_pathogens(self):
        labels = {p["expected"] for p in dvg.PATHOGENS if p["role"] == "target"}
        assert {"Salmonella", "E.coli/Shigella", "V.parahaemolyticus"} <= labels

    def test_negative_controls_present(self):
        roles = {p["role"] for p in dvg.PATHOGENS}
        assert "negative" in roles

    def test_every_entry_has_taxon_and_expected(self):
        for p in dvg.PATHOGENS:
            assert p["taxon"] and p["expected"] and p["role"] in ("target", "negative")


class TestParseSummary:
    def test_filters_level_and_category(self):
        accessions = dvg.parse_summary(SUMMARY_JSON_LINES)
        assert accessions == ["GCF_000006945.2"]

    def test_caps_per_taxon(self):
        promoted = SUMMARY_JSON_LINES.replace(
            '"assembly_level": "Contig"',
            '"assembly_level": "Chromosome"',
        )
        accessions = dvg.parse_summary(promoted, cap=2)
        assert accessions == ["GCF_000006945.2", "GCF_000195995.1"]

    def test_accepts_aggregated_reports_json(self):
        reports = [json.loads(ln) for ln in SUMMARY_JSON_LINES.splitlines()]
        accessions = dvg.parse_summary(json.dumps({"reports": reports}))
        assert accessions == ["GCF_000006945.2"]

    def test_malformed_json_returns_empty(self):
        assert dvg.parse_summary("{not json") == []

    def test_empty_reports(self):
        assert dvg.parse_summary('{"reports": []}') == []


class TestManifest:
    def test_manifest_rows_written(self, tmp_path):
        rows = [
            ("GCF_1", "Salmonella enterica", "Salmonella", "target"),
            ("GCF_2", "Vibrio vulnificus", "V.vulnificus_negative", "negative"),
        ]
        path = dvg.write_manifest(tmp_path, rows)
        lines = path.read_text().strip().splitlines()
        assert lines[0] == "accession\torganism\texpected\trole\tfna"
        assert len(lines) == 3

    def test_fna_resolved_when_present(self, tmp_path):
        fna = tmp_path / "genomes" / "GCF_1_ASM1v1_genomic.fna"
        fna.parent.mkdir(parents=True)
        fna.write_text(">x\n")
        path = dvg.write_manifest(
            tmp_path, [("GCF_1", "Salmonella enterica", "Salmonella", "target")]
        )
        assert "GCF_1_ASM1v1_genomic.fna" in path.read_text()


class TestSummaryCommand:
    def test_command_shape(self):
        cmd = dvg.summary_command("Salmonella enterica")
        assert "datasets" in cmd[0] or cmd[0].endswith("datasets")
        assert "summary" in cmd
        assert "Salmonella enterica" in cmd
        assert "--assembly-source" in cmd and "RefSeq" in cmd


FTP_LISTING = """Index of /pathogen/Results
<pre>Name
<a href="BioProject_Hierarchy/">BioProject_Hierarchy/</a>
<a href="Escherichia_coli_Shigella/">Escherichia_coli_Shigella/</a>
<a href="Salmonella/">Salmonella/</a>
<a href="Vibrio_alginolyticus/">Vibrio_alginolyticus/</a>
<a href="Vibrio_parahaemolyticus/">Vibrio_parahaemolyticus/</a>
</pre>
"""


class TestTrackedGroups:
    def test_parse_ftp_listing(self):
        groups = dvg.parse_ftp_listing(FTP_LISTING)
        assert groups == [
            "Escherichia_coli_Shigella",
            "Salmonella",
            "Vibrio_alginolyticus",
            "Vibrio_parahaemolyticus",
        ]

    def test_taxon_to_group_slug(self):
        assert dvg.taxon_to_group("Salmonella enterica") == "Salmonella_enterica"

    def test_verify_passes_for_tracked(self):
        findings = dvg.verify_against_tracked_groups(
            [{"taxon": "Salmonella enterica", "expected": "x", "role": "target"}],
            tracked={"Salmonella", "Escherichia_coli_Shigella"},
        )
        assert findings == []

    def test_verify_flags_untracked(self):
        findings = dvg.verify_against_tracked_groups(
            [{"taxon": "Madeup fakeus", "expected": "x", "role": "target"}],
            tracked={"Salmonella"},
        )
        assert len(findings) == 1
        assert "Madeup fakeus" in findings[0]

    def test_verify_uses_group_aliases(self):
        findings = dvg.verify_against_tracked_groups(
            [
                {"taxon": "Escherichia coli", "expected": "x", "role": "target"},
                {"taxon": "Shigella", "expected": "x", "role": "target"},
                {"taxon": "Klebsiella pneumoniae", "expected": "x", "role": "negative"},
                {"taxon": "Listeria monocytogenes", "expected": "x", "role": "negative"},
                {"taxon": "Campylobacter jejuni", "expected": "x", "role": "negative"},
            ],
            tracked={
                "Escherichia_coli_Shigella",
                "Klebsiella",
                "Listeria",
                "Campylobacter",
            },
        )
        assert findings == []
