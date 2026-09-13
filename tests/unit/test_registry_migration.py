"""Migration contract tests (R0): rewired call sites equal pre-refactor literals.

Every hardcoded dict that used to live in the .smk rule files and
species_identifier.py must be byte-for-byte reproducible from the registry
via get_workflow_tables(). This is the unit-level half of the migration
proof; the DAG-level half is the snakemake dry-run comparison.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


class TestSpeciesIdentifierRewired:
    def test_module_dicts_equal_golden(self):
        from hermes_bacmap.analysis import species_identifier

        assert species_identifier._GENE_TO_SPECIES == {
            "inva": ("Salmonella", "high"),
            "uida": ("DEC", "high"),
            "ipah": ("Shigella/EIEC", "high"),
            "toxr": ("V_parahaemolyticus", "high"),
            "tlh": ("V_parahaemolyticus", "high"),
        }
        assert species_identifier._SPECIES_PRIORITY == ["inva", "ipah", "toxr", "tlh", "uida"]

    def test_dicts_derived_from_registry(self):
        """The module-level dicts must be BUILT FROM the registry, not literals."""
        from hermes_bacmap.analysis import species_identifier
        from hermes_bacmap.pathogen_registry import load_registry

        gene_map, priority = load_registry().species_markers()
        assert species_identifier._GENE_TO_SPECIES == dict(gene_map)
        assert species_identifier._SPECIES_PRIORITY == priority


class TestWorkflowTables:
    """get_workflow_tables() is the single object the Snakefile/rules consume."""

    def test_tables_exist_and_match_rule_literals(self):
        from hermes_bacmap.pathogen_registry import get_workflow_tables

        t = get_workflow_tables()

        assert t.mlst_schemes == {
            "Salmonella": "salmonella_2",
            "E.coli": "ecoli_1",
            "Shigella": "ecoli_1",
            "V.parahaemolyticus": "vparahaemolyticus_1",
        }
        assert t.amrfinder_organisms == {
            "Salmonella": "Salmonella",
            "E.coli": "Escherichia",
            # V.parahaemolyticus deliberately absent (no curated AMRFinderPlus
            # organism DB) — adding it would change rule behaviour.
            "Shigella": "Escherichia",
        }

        # mirrors rules/cgmlst.smk _CGMLST_SCHEMES
        assert t.cgmlst_schemes == {
            "Salmonella": "senterica_2",
            "E.coli": "ecoli_2",
            "Shigella": "ecoli_2",
            "V.parahaemolyticus": "vparahaemolyticus_3",
        }

        # mirrors rules/snp.smk _SPECIES_GROUPS (refs resolved to absolute)
        assert set(t.snp_groups) == {"salmonella", "ecoli", "vpara"}
        assert t.snp_groups["ecoli"]["species"] == ["E.coli", "Shigella"]
        assert t.snp_groups["ecoli"]["organism"] == "Escherichia coli / Shigella"
        assert t.snp_groups["salmonella"]["ref"].endswith(
            "data/reference/genomes/salmonella_LT2.fasta"
        )
        assert t.snp_groups["vpara"]["ref"].endswith("data/reference/genomes/vpara_rimd.fasta")

    def test_cgmlst_species_groups(self):
        from hermes_bacmap.pathogen_registry import get_workflow_tables

        t = get_workflow_tables()
        # mirrors rules/cgmlst.smk _CGMLST_SPECIES_GROUPS
        assert t.cgmlst_species_groups == {
            "salmonella": {
                "species": ["Salmonella"],
                "organism": "Salmonella enterica",
                "scheme": "senterica_2",
            },
            "ecoli": {
                "species": ["E.coli", "Shigella"],
                "organism": "Escherichia coli / Shigella",
                "scheme": "ecoli_2",
            },
            "vpara": {
                "species": ["V.parahaemolyticus"],
                "organism": "Vibrio parahaemolyticus",
                "scheme": "vparahaemolyticus_3",
            },
        }

    def test_tables_are_stable_per_process(self):
        from hermes_bacmap.pathogen_registry import get_workflow_tables

        assert get_workflow_tables() is get_workflow_tables()


class TestRegistrySignature:
    """Registry content hash for the evidence chain (database_signature)."""

    def test_signature_stable_and_hex(self):
        from hermes_bacmap.pathogen_registry import load_registry

        sig = load_registry().signature()
        assert isinstance(sig, str)
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)
        assert load_registry().signature() == sig

    def test_signature_changes_with_content(self, tmp_path):
        import yaml

        from hermes_bacmap.pathogen_registry import load_registry

        base = {
            "pathogens": {
                "Salmonella": {
                    "display_name": "s",
                    "marker_genes": ["inva"],
                    "mlst_scheme": "salmonella_2",
                    "snp_group": "g1",
                }
            },
            "snp_groups": {
                "g1": {
                    "ref": "data/reference/genomes/salmonella_LT2.fasta",
                    "species": ["Salmonella"],
                    "organism": "S",
                }
            },
        }
        p1 = tmp_path / "a.yaml"
        p1.write_text(yaml.safe_dump(base), encoding="utf-8")
        s1 = load_registry(p1).signature()

        base["pathogens"]["Salmonella"]["display_name"] = "changed"
        p2 = tmp_path / "b.yaml"
        p2.write_text(yaml.safe_dump(base), encoding="utf-8")
        assert load_registry(p2).signature() != s1
