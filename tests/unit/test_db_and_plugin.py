"""Tests for hermes_bacmap.db (path resolution) and hermes_bacmap.__init__ (register())."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap import db as db_module  # noqa: E402
from hermes_bacmap import register  # noqa: E402
from hermes_bacmap.config import REF_DIR  # noqa: E402


class TestDbConstants:
    def test_all_paths_are_under_ref_dir(self):
        constants = [
            db_module.SPECIES_MARKERS,
            db_module.AMR_CARD,
            db_module.AMR_VFDB,
            db_module.PLASMIDFINDER,
            db_module.SEROTYPE_ECOH,
            db_module.SEROTYPE_SHIGELLA,
            db_module.VIRULENCE_TDH,
            db_module.VIRULENCE_TRH,
            db_module.VIRULENCE_VPARA_TARGETS,
            db_module.GENOME_SALMONELLA_LT2,
            db_module.GENOME_ECOLI_K12,
            db_module.GENOME_VPARA_RIMD,
            db_module.ANNOTATION_PROKKA_SPROT,
            db_module.ANNOTATION_PROKKA_IS,
            db_module.ANNOTATION_PROKKA_AMR,
            db_module.VPA_SEROTYPE_DIR,
        ]
        for p in constants:
            assert isinstance(p, Path), f"{p!r} is not a Path"
            assert REF_DIR in p.parents or p == REF_DIR, f"{p} not under REF_DIR={REF_DIR}"

    def test_db_name_to_source_keys(self):
        for key in (
            "species_markers",
            "card",
            "vfdb",
            "plasmidfinder",
            "ecoh",
            "ecoh_sequences",
            "shigella_ref",
            "shigella",
            "tdh",
            "trh",
            "vpara_targets",
            "prokka_sprot",
            "prokka_is",
            "prokka_amr",
        ):
            assert key in db_module.DB_NAME_TO_SOURCE, f"missing key {key!r}"

    def test_db_name_to_source_values_are_paths(self):
        for name, path in db_module.DB_NAME_TO_SOURCE.items():
            assert isinstance(path, Path), f"{name!r} maps to non-Path {path!r}"

    def test_aliases_resolve_to_same_path(self):
        assert db_module.DB_NAME_TO_SOURCE["ecoh"] == db_module.DB_NAME_TO_SOURCE["ecoh_sequences"]
        assert (
            db_module.DB_NAME_TO_SOURCE["shigella_ref"] == db_module.DB_NAME_TO_SOURCE["shigella"]
        )

    def test_snp_references_keys(self):
        for key in ("salmonella", "ecoli", "vpara"):
            assert key in db_module.SNP_REFERENCES
            assert isinstance(db_module.SNP_REFERENCES[key], Path)


class TestResolveSource:
    def test_hit_returns_path(self):
        p = db_module.resolve_source("card")
        assert p is db_module.DB_NAME_TO_SOURCE["card"]

    def test_miss_returns_none(self):
        assert db_module.resolve_source("no_such_db_in_table") is None

    def test_none_arg_safe(self):
        assert db_module.resolve_source("") is None


class FakeCtx:
    def __init__(self) -> None:
        self.tools: list[dict] = []
        self.skills: list[tuple[str, Path]] = []

    def register_tool(
        self,
        *,
        name: str,
        toolset: str,
        schema: dict,
        handler,  # noqa: ANN001
    ) -> None:
        self.tools.append({"name": name, "toolset": toolset, "schema": schema, "handler": handler})

    def register_skill(self, name: str, path: Path) -> None:
        self.skills.append((name, Path(path)))


def _expected_skill_names() -> list[str]:
    skills_dir = _PROJECT_ROOT / "src" / "hermes_bacmap" / "skills"
    if not skills_dir.is_dir():
        return []
    names = []
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            names.append(child.name)
    return names


class TestRegister:
    def test_register_returns_none_and_records_24_tools(self):
        ctx = FakeCtx()
        result = register(ctx)
        assert result is None
        assert len(ctx.tools) == 24, f"expected 24 tools, got {len(ctx.tools)}"

    def test_all_tool_names_start_with_bio(self):
        ctx = FakeCtx()
        register(ctx)
        for entry in ctx.tools:
            assert entry["name"].startswith("bio_"), entry["name"]

    def test_all_toolsets_are_bioinfo(self):
        ctx = FakeCtx()
        register(ctx)
        for entry in ctx.tools:
            assert entry["toolset"] == "bioinfo", entry["name"]

    def test_all_schemas_are_dicts(self):
        ctx = FakeCtx()
        register(ctx)
        for entry in ctx.tools:
            assert isinstance(entry["schema"], dict), entry["name"]
            assert "name" in entry["schema"] or "type" in entry["schema"], entry["name"]

    def test_all_handlers_are_callable(self):
        ctx = FakeCtx()
        register(ctx)
        for entry in ctx.tools:
            assert callable(entry["handler"]), entry["name"]

    def test_no_duplicate_tool_names(self):
        ctx = FakeCtx()
        register(ctx)
        names = [t["name"] for t in ctx.tools]
        assert len(names) == len(set(names)), "duplicate tool names registered"

    def test_expected_tool_names_present(self):
        ctx = FakeCtx()
        register(ctx)
        names = {t["name"] for t in ctx.tools}
        expected = {
            "bio_seq_stats",
            "bio_seq_ops",
            "bio_fastq_qc",
            "bio_seq_convert",
            "bio_blast",
            "bio_align",
            "bio_samtools",
            "bio_variant",
            "bio_analyze_pathogen",
            "bio_get_result",
            "bio_verify_result",
            "bio_generate_report",
            "bio_list_samples",
            "bio_gene_scan",
            "bio_snp_tree",
            "bio_search_samples",
            "bio_annotate",
            "bio_validate_taxonomy",
            "bio_diagnose",
            "bio_vpa_serotype",
            "bio_query_metadata",
            "bio_add_metadata",
            "bio_query_lab_results",
            "bio_add_lab_result",
        }
        assert expected <= names, f"missing: {expected - names}"

    def test_skills_registered_match_filesystem(self):
        ctx = FakeCtx()
        register(ctx)
        expected = _expected_skill_names()
        got_names = [name for name, _ in ctx.skills]
        assert got_names == expected, f"skill mismatch — got {got_names!r}, expected {expected!r}"

    def test_registered_skill_paths_exist_and_match_name(self):
        ctx = FakeCtx()
        register(ctx)
        for name, path in ctx.skills:
            assert path.exists(), f"skill {name} -> missing {path}"
            assert path.parent.name == name, f"skill dir name mismatch for {name}"

    def test_skill_count_is_at_least_one_when_dir_present(self):
        ctx = FakeCtx()
        register(ctx)
        skills_dir = _PROJECT_ROOT / "src" / "hermes_bacmap" / "skills"
        if skills_dir.is_dir() and any(skills_dir.iterdir()):
            assert len(ctx.skills) >= 1, "no skills registered despite skills/ dir present"
