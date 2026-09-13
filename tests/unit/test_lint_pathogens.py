"""Tests for ``scripts/lint_pathogens.py`` (offline registry consistency checks)."""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

_SPEC = importlib.util.spec_from_file_location(
    "lint_pathogens", _PROJECT_ROOT / "scripts" / "lint_pathogens.py"
)
lint_pathogens = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(lint_pathogens)

CLEAN_REGISTRY = textwrap.dedent(
    """\
    pathogens:
      Testomonas:
        display_name: 测试菌
        marker_genes: [tstA]
        mlst_scheme: testomonas_1
        snp_group: tstgroup
    snp_groups:
      tstgroup:
        ref: data/reference/genomes/salmonella_LT2.fasta
        species: [Testomonas]
        organism: Testomonas test
    """
)

MARKERS_WITH_TSTA = ">species_markers~~~tstA~~~XX000001.1 test marker\nACGT\n"


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


class TestRunLint:
    def test_clean_registry_no_findings(self, tmp_path):
        reg = _write(tmp_path, "pathogens.yaml", CLEAN_REGISTRY)
        markers = _write(tmp_path, "markers.fasta", MARKERS_WITH_TSTA)
        assert lint_pathogens.run_lint(reg, None, markers) == []

    def test_marker_missing_from_fasta_reported(self, tmp_path):
        reg = _write(tmp_path, "pathogens.yaml", CLEAN_REGISTRY)
        markers = _write(tmp_path, "markers.fasta", ">species_markers~~~other~~~X.1\nACGT\n")
        findings = lint_pathogens.run_lint(reg, None, markers)
        assert any("tsta" in f for f in findings)

    def test_unregistered_species_in_samples_reported(self, tmp_path):
        reg = _write(tmp_path, "pathogens.yaml", CLEAN_REGISTRY)
        markers = _write(tmp_path, "markers.fasta", MARKERS_WITH_TSTA)
        samples = _write(
            tmp_path,
            "samples.tsv",
            "sample\tspecies\tR1\tR2\nS1\tTestomonas\ta\tb\nS2\tUnknownus\tc\td\n",
        )
        findings = lint_pathogens.run_lint(reg, samples, markers)
        assert any("Unknownus" in f for f in findings)
        assert not any("Testomonas" in f for f in findings)

    def test_disabled_species_in_samples_reported(self, tmp_path):
        reg = _write(
            tmp_path,
            "pathogens.yaml",
            CLEAN_REGISTRY.replace(
                "snp_group: tstgroup", "snp_group: tstgroup\n    enabled: false"
            ),
        )
        markers = _write(tmp_path, "markers.fasta", MARKERS_WITH_TSTA)
        samples = _write(
            tmp_path,
            "samples.tsv",
            "sample\tspecies\tR1\tR2\nS1\tTestomonas\ta\tb\n",
        )
        findings = lint_pathogens.run_lint(reg, samples, markers)
        assert any("disabled" in f and "Testomonas" in f for f in findings)

    def test_missing_snp_reference_reported(self, tmp_path):
        reg = _write(
            tmp_path,
            "pathogens.yaml",
            CLEAN_REGISTRY.replace("salmonella_LT2.fasta", "does_not_exist_anywhere.fasta"),
        )
        markers = _write(tmp_path, "markers.fasta", MARKERS_WITH_TSTA)
        findings = lint_pathogens.run_lint(reg, None, markers)
        assert any("does_not_exist_anywhere" in f for f in findings)


class TestMain:
    def test_exit_code_nonzero_on_findings(self, tmp_path, monkeypatch, capsys):
        reg = _write(tmp_path, "pathogens.yaml", CLEAN_REGISTRY)
        markers = _write(tmp_path, "markers.fasta", ">species_markers~~~zzz~~~X.1\nACGT\n")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "lint_pathogens",
                "--registry",
                str(reg),
                "--markers",
                str(markers),
                "--samples",
                str(tmp_path / "no_samples.tsv"),
            ],
        )
        code = lint_pathogens.main()
        assert code == 1
        assert "tsta" in capsys.readouterr().out

    def test_exit_code_zero_when_clean(self, tmp_path, monkeypatch):
        reg = _write(tmp_path, "pathogens.yaml", CLEAN_REGISTRY)
        markers = _write(tmp_path, "markers.fasta", MARKERS_WITH_TSTA)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "lint_pathogens",
                "--registry",
                str(reg),
                "--markers",
                str(markers),
                "--samples",
                str(tmp_path / "no_samples.tsv"),
            ],
        )
        assert lint_pathogens.main() == 0
