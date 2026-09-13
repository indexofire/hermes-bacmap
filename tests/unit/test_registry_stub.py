"""Stub-pathogen smoke tests (R0 acceptance): adding a pathogen requires zero .smk edits."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

STUB_REGISTRY = textwrap.dedent(
    """\
    pathogens:
      Testomonas:
        display_name: 测试菌
        marker_genes: [tstA, tstB]
        mlst_scheme: testomonas_1
        cgmlst_scheme: testomonas_cg
        snp_group: tstgroup
    snp_groups:
      tstgroup:
        ref: data/reference/genomes/salmonella_LT2.fasta
        species: [Testomonas]
        organism: Testomonas testus
    """
)


def _write_stub(tmp_path: Path) -> Path:
    p = tmp_path / "stub_pathogens.yaml"
    p.write_text(STUB_REGISTRY, encoding="utf-8")
    return p


class TestStubRegistryQueries:
    def test_stub_pathogen_in_all_query_tables(self, tmp_path):
        from hermes_bacmap.pathogen_registry import load_registry

        reg = load_registry(_write_stub(tmp_path))
        assert reg.mlst_schemes() == {"Testomonas": "testomonas_1"}
        assert reg.cgmlst_schemes() == {"Testomonas": "testomonas_cg"}
        gene_map, priority = reg.species_markers()
        assert gene_map == {
            "tsta": ("Testomonas", "high"),
            "tstb": ("Testomonas", "high"),
        }
        assert priority == ["tsta", "tstb"]


class TestSpeciesIdentifierHonoursEnvOverride:
    def test_module_dicts_built_from_env_registry(self, tmp_path):
        env = {
            **os.environ,
            "BACMAP_PATHOGEN_REGISTRY": str(_write_stub(tmp_path)),
        }
        code = (
            "from hermes_bacmap.analysis.species_identifier import ("
            "_GENE_TO_SPECIES, _SPECIES_PRIORITY); "
            "assert _GENE_TO_SPECIES['tsta'] == ('Testomonas', 'high'); "
            "assert _SPECIES_PRIORITY == ['tsta', 'tstb']"
        )
        res = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
        )
        assert res.returncode == 0, res.stderr
