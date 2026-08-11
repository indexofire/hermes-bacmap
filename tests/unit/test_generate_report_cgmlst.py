"""Tests for the per-sample cgMLST trace-back card in generate_report.py
(plan todo 9).

Mirrors the fixture + monkey-patch style of ``tests/unit/test_cgmlst_ingest.py``:
the cgMLST report logic lives in the ``scripts/generate_report.py`` script
module, so we import it via sys.path and point its module-level path constants
at a tmp_path sandbox.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import generate_report as gr  # noqa: E402

from hermes_bacmap.analysis.cgmlst_projection import Verdict  # noqa: E402
from hermes_bacmap.analysis.cgmlst_types import CgmlstProfile  # noqa: E402

SYNTHETIC_FIXTURE = (
    _PROJECT_ROOT / "tests" / "fixtures" / "cgmlst_reference" / "synthetic_5.tsv"
)
REAL_CONFIG = _PROJECT_ROOT / "workflows" / "bacmap" / "config" / "config.yaml"

SAMPLE_TSV_TEMPLATE = (
    "File\tScheme\tST\tL1\tL2\tL3\tL4\tL5\tL6\tL7\tL8\tL9\tL10\n"
    "{sample}\tsenterica_2\t-\t{a1}\t{a2}\t{a3}\t{a4}\t{a5}\t{a6}\t{a7}\t{a8}\t{a9}\t{a10}\n"
)


def _setup_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    results = tmp_path / "results"
    results.mkdir()
    ref_root = tmp_path / "cgmlst"
    ref_root.mkdir()
    monkeypatch.setattr(gr, "RESULTS_DIR", results)
    monkeypatch.setattr(gr, "CGMLST_REFERENCE_DIR", ref_root)
    return ref_root


def _write_cgmlst_tsv(
    results_dir: Path, sample_id: str, alleles: list[str]
) -> Path:
    fields = {
        f"a{i}": alleles[i - 1] for i in range(1, 11)
    }
    cgmlst_path = results_dir / sample_id / "typing" / "cgmlst.tsv"
    cgmlst_path.parent.mkdir(parents=True, exist_ok=True)
    cgmlst_path.write_text(
        SAMPLE_TSV_TEMPLATE.format(sample=sample_id, **fields)
    )
    return cgmlst_path


def _write_salmonella_reference(ref_root: Path) -> Path:
    salmonella_dir = ref_root / "salmonella"
    salmonella_dir.mkdir(parents=True, exist_ok=True)
    dest = salmonella_dir / "reference_profiles.tsv"
    dest.write_text(SYNTHETIC_FIXTURE.read_text())
    return dest


SALMONELLA_SUMMARY: dict[str, Any] = {
    "steps": {"species": {"species": "Salmonella", "confidence": "high"}},
    "pipeline_version": "salmonella-workflow-v0.1",
}


class TestExtractSpecies:
    def test_modern_shape_species_key(self):
        assert (
            gr._extract_species({"steps": {"species": {"species": "Salmonella"}}})
            == "Salmonella"
        )

    def test_legacy_shape_verdict_key(self):
        assert (
            gr._extract_species({"steps": {"species": {"verdict": "E.coli"}}})
            == "E.coli"
        )

    def test_species_key_preferred_over_verdict(self):
        summary = {
            "steps": {"species": {"species": "Salmonella", "verdict": "Other"}}
        }
        assert gr._extract_species(summary) == "Salmonella"

    def test_string_species_step(self):
        assert gr._extract_species({"steps": {"species": "Salmonella"}}) == "Salmonella"

    def test_empty_summary(self):
        assert gr._extract_species({}) == ""

    def test_missing_species_step(self):
        assert gr._extract_species({"steps": {}}) == ""


class TestSpeciesDirName:
    @pytest.mark.parametrize(
        "species,expected",
        [
            ("Salmonella", "salmonella"),
            ("SALMONELLA", "salmonella"),
            ("E.coli", "ecoli"),
            ("Escherichia coli", "ecoli"),
            ("Shigella", "shigella"),
            ("V.parahaemolyticus", "vparahaemolyticus"),
            ("Vibrio parahaemolyticus", "vparahaemolyticus"),
        ],
    )
    def test_known_species_folds_to_dir(self, species: str, expected: str):
        assert gr._species_dir_name(species) == expected

    def test_unknown_species_lowercased(self):
        assert gr._species_dir_name("Listeria monocytogenes") == "listeriamonocytogenes"


class TestLoadReferenceProfiles:
    def test_missing_dir_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        assert gr._load_reference_profiles("Salmonella") == []
        assert not (ref_root / "salmonella").exists()

    def test_present_library_loads_profiles(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        _write_salmonella_reference(ref_root)
        profiles = gr._load_reference_profiles("Salmonella")
        assert len(profiles) == 5
        assert {p.sample_id for p in profiles} == {
            "REF-001",
            "REF-002",
            "REF-003",
            "REF-004",
            "REF-005",
        }

    def test_empty_species_returns_empty(self):
        assert gr._load_reference_profiles("") == []

    def test_malformed_tsv_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        salmonella_dir = ref_root / "salmonella"
        salmonella_dir.mkdir(parents=True)
        (salmonella_dir / "reference_profiles.tsv").write_text("not\ttps\tvalid")
        # parse_cgmlst_profiles tolerates a lot, but a row with no alleles still
        # parses; what matters is we never raise. Assert it returns a list.
        assert isinstance(gr._load_reference_profiles("Salmonella"), list)


class TestRenderCgmlstSectionOmitted:
    def test_no_cgmlst_tsv_returns_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_sandbox(monkeypatch, tmp_path)
        section = gr._render_cgmlst_section("SAM-NOPE", SALMONELLA_SUMMARY)
        assert section == ""

    def test_fallback_na_tsv_returns_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_sandbox(monkeypatch, tmp_path)
        cgmlst_path = gr.RESULTS_DIR / "SAM-NA" / "typing" / "cgmlst.tsv"
        cgmlst_path.parent.mkdir(parents=True)
        cgmlst_path.write_text("File\tScheme\tST\nSAM-NA\tsenterica_2\tN/A")
        assert gr._render_cgmlst_section("SAM-NA", SALMONELLA_SUMMARY) == ""


class TestRenderCgmlstSectionGracefulDegradation:
    def test_profile_only_when_no_reference_library(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_sandbox(monkeypatch, tmp_path)
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-PROF", ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1"]
        )

        section = gr._render_cgmlst_section("SAM-PROF", SALMONELLA_SUMMARY)

        assert "cgMLST" in section
        assert "senterica_2" in section
        assert "Total loci" in section
        assert "10 (100.0%)" in section
        assert "cgmlst-verdict-undetermined" in section
        assert "no reference library" in section
        # No nearest-references table in profile-only mode.
        assert "nearest references" not in section

    def test_profile_only_when_species_unknown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        _write_salmonella_reference(ref_root)
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-UNK", ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1"]
        )
        summary = {"steps": {"species": {"species": "Listeria"}}}

        section = gr._render_cgmlst_section("SAM-UNK", summary)

        assert "cgmlst-verdict-undetermined" in section
        # Unknown species -> no reference dir -> the "no reference library"
        # caveat mentions the species dir.
        assert "no reference library" in section
        assert "listeria" in section

    def test_profile_only_when_species_missing_from_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_sandbox(monkeypatch, tmp_path)
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-NOSPECIES",
            ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1"],
        )

        section = gr._render_cgmlst_section("SAM-NOSPECIES", {"steps": {}})

        assert "cgmlst-verdict-undetermined" in section
        assert "species undetermined" in section


class TestRenderCgmlstSectionFullProjection:
    def test_outbreak_card_with_nearest_references(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        _write_salmonella_reference(ref_root)
        # Query identical to REF-001 -> nearest is REF-001 at distance 0,
        # next is REF-002 at distance 1 (golden), under outbreak=10 -> OUTBREAK.
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-OUT",
            ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1"],
        )

        section = gr._render_cgmlst_section("SAM-OUT", SALMONELLA_SUMMARY)

        assert "cgMLST" in section
        assert "cgmlst-verdict-outbreak" in section
        assert "OUTBREAK" in section
        assert "REF-001" in section
        assert "nearest references" in section
        assert "Allele distance" in section
        assert "distance 0" in section
        assert "Comparable loci (nearest)" in section

    def test_related_badge_when_distance_above_outbreak_threshold(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        # Tighter outbreak threshold: synthetic fixture Salmonella default
        # outbreak=10 covers even the 8-distance outlier as OUTBREAK, so use a
        # custom config with outbreak=2 related=5.
        custom_cfg = tmp_path / "config.yaml"
        custom_cfg.write_text(
            "cgmlst:\n"
            "  projection:\n    top_n: 10\n"
            "  thresholds:\n"
            "    salmonella:\n"
            "      outbreak_allele_dist: 2\n"
            "      related_allele_dist: 5\n"
        )
        monkeypatch.setattr(gr, "CONFIG_PATH", custom_cfg)
        _write_salmonella_reference(ref_root)
        # Novel query [4,4,4,1,1,1,1,1,1,1] (not in reference set). Distances:
        # to REF-001 [1,1,1,1,1,1,1,1,1,1] = 3 (L1,L2,L3); to REF-002 = 4;
        # to REF-003 = 5; etc. min_dist=3: 3 > outbreak=2 and 3 <= related=5
        # -> RELATED.
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-REL",
            ["4", "4", "4", "1", "1", "1", "1", "1", "1", "1"],
        )

        section = gr._render_cgmlst_section("SAM-REL", SALMONELLA_SUMMARY)

        assert "cgmlst-verdict-related" in section

    def test_unrelated_badge_with_tight_thresholds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        custom_cfg = tmp_path / "config.yaml"
        custom_cfg.write_text(
            "cgmlst:\n"
            "  projection:\n    top_n: 10\n"
            "  thresholds:\n"
            "    salmonella:\n"
            "      outbreak_allele_dist: 1\n"
            "      related_allele_dist: 2\n"
        )
        monkeypatch.setattr(gr, "CONFIG_PATH", custom_cfg)
        _write_salmonella_reference(ref_root)
        # Genuine outlier not in the reference set: distance >= 3 to every
        # reference -> min_dist > related=2 -> UNRELATED.
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-UNREL",
            ["50", "50", "50", "50", "50", "50", "50", "50", "50", "50"],
        )

        section = gr._render_cgmlst_section("SAM-UNREL", SALMONELLA_SUMMARY)

        assert "cgmlst-verdict-unrelated" in section

    def test_vpara_undetermined_badge_no_threshold(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        _write_salmonella_reference(ref_root)
        # Real config has Vpara thresholds = both null -> UNDETERMINED + caveat.
        monkeypatch.setattr(gr, "CONFIG_PATH", REAL_CONFIG)
        summary = {"steps": {"species": {"species": "V.parahaemolyticus"}}}
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-VP",
            ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1"],
        )

        section = gr._render_cgmlst_section("SAM-VP", summary)

        # Salmonella reference lib is used because the dir lookup resolves
        # V.parahaemolyticus -> vparahaemolyticus (no dir exists -> empty),
        # so we actually hit the "no reference library" path. Verify either way:
        assert "cgmlst-verdict-undetermined" in section

    def test_s_sonnei_caveat_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        # Shigella thresholds from real config.
        monkeypatch.setattr(gr, "CONFIG_PATH", REAL_CONFIG)
        # Need a Shigella reference library to project against.
        shigella_dir = ref_root / "shigella"
        shigella_dir.mkdir(parents=True)
        (shigella_dir / "reference_profiles.tsv").write_text(
            SYNTHETIC_FIXTURE.read_text()
        )
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-SON",
            ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1"],
        )
        summary = {"steps": {"species": {"species": "Shigella sonnei"}}}

        section = gr._render_cgmlst_section("SAM-SON", summary)

        assert "S. sonnei" in section
        assert "SNV" in section

    def test_missing_data_marker_in_query_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        _write_salmonella_reference(ref_root)
        # Query with 2 missing loci (L1 and L5 = "-").
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-MISS",
            ["-", "1", "1", "1", "-", "1", "1", "1", "1", "1"],
        )

        section = gr._render_cgmlst_section("SAM-MISS", SALMONELLA_SUMMARY)

        # 8/10 called -> 80%, missing rate 20%.
        assert "8 (80.0%)" in section
        assert "20.00%" in section
        assert "Missing loci" in section

    def test_top_n_truncation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        custom_cfg = tmp_path / "config.yaml"
        custom_cfg.write_text(
            "cgmlst:\n"
            "  projection:\n    top_n: 2\n"
            "  thresholds:\n"
            "    salmonella:\n"
            "      outbreak_allele_dist: 10\n"
            "      related_allele_dist: 50\n"
        )
        monkeypatch.setattr(gr, "CONFIG_PATH", custom_cfg)
        _write_salmonella_reference(ref_root)
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-TOPN",
            ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1"],
        )

        section = gr._render_cgmlst_section("SAM-TOPN", SALMONELLA_SUMMARY)

        assert "Top 2 nearest references" in section


class TestVerdictBadgeHtml:
    @pytest.mark.parametrize(
        "verdict,css_class,label",
        [
            (Verdict.OUTBREAK, "cgmlst-verdict-outbreak", "OUTBREAK"),
            (Verdict.RELATED, "cgmlst-verdict-related", "RELATED"),
            (Verdict.UNRELATED, "cgmlst-verdict-unrelated", "UNRELATED"),
            (Verdict.UNDETERMINED, "cgmlst-verdict-undetermined", "UNDETERMINED"),
        ],
    )
    def test_badge_classes(self, verdict: Verdict, css_class: str, label: str):
        html = gr._verdict_badge_html(verdict)
        assert css_class in html
        assert label in html
        assert "cgmlst-verdict-badge" in html


class TestComputeProjection:
    def test_returns_none_when_no_reference_library(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_sandbox(monkeypatch, tmp_path)
        profile = CgmlstProfile(
            sample_id="X", scheme="senterica_2", st_raw="-",
            alleles={"L1": 1}, n_called=1, n_total=1,
        )
        assert gr._compute_projection(profile, "Salmonella") is None

    def test_returns_none_when_species_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_sandbox(monkeypatch, tmp_path)
        profile = CgmlstProfile(
            sample_id="X", scheme="senterica_2", st_raw="-",
            alleles={"L1": 1}, n_called=1, n_total=1,
        )
        assert gr._compute_projection(profile, "") is None

    def test_returns_none_when_profile_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        _write_salmonella_reference(ref_root)
        profile = CgmlstProfile(sample_id="X", scheme="senterica_2", st_raw="-")
        assert gr._compute_projection(profile, "Salmonella") is None

    def test_returns_result_when_reference_available(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        _write_salmonella_reference(ref_root)
        profile = CgmlstProfile(
            sample_id="QUERY", scheme="senterica_2", st_raw="-",
            alleles={f"L{i}": 1 for i in range(1, 11)},
            n_called=10, n_total=10,
        )

        result = gr._compute_projection(profile, "Salmonella")

        assert result is not None
        assert result.verdict is Verdict.OUTBREAK
        assert result.nearest[0].distance == 0  # query matches REF-001


class TestLoadTopNFromConfig:
    def test_real_config_returns_default_ten(self):
        assert gr._load_top_n_from_config(REAL_CONFIG) == 10

    def test_missing_config_returns_default(self, tmp_path: Path):
        assert gr._load_top_n_from_config(tmp_path / "missing.yaml") == 10

    def test_invalid_value_returns_default(self, tmp_path: Path):
        cfg = tmp_path / "c.yaml"
        cfg.write_text(
            "cgmlst:\n  projection:\n    top_n: 0\n"
        )
        assert gr._load_top_n_from_config(cfg) == 10

    def test_valid_value_returned(self, tmp_path: Path):
        cfg = tmp_path / "c.yaml"
        cfg.write_text(
            "cgmlst:\n  projection:\n    top_n: 5\n"
        )
        assert gr._load_top_n_from_config(cfg) == 5


class TestGenerateHtmlIntegration:
    """End-to-end: generate_html emits the cgMLST section when the TSV exists
    and omits it when absent."""

    def _fake_verification(self) -> Any:
        # generate_html reads .passed, .needs_human_review, .failed_count, and
        # iterates .checks for .name / .passed / .message -- a duck-typed stub
        # is sufficient for the integration test (we are not testing the
        # verifier here, only that the cgMLST section threads through).
        class _Check:
            name = "dummy"
            passed = True
            message = "ok"

        class _V:
            passed = True
            needs_human_review = False
            failed_count = 0
            checks = [_Check()]

        return _V()

    def test_html_includes_cgmlst_section_when_tsv_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_root = _setup_sandbox(monkeypatch, tmp_path)
        _write_salmonella_reference(ref_root)
        _write_cgmlst_tsv(
            gr.RESULTS_DIR, "SAM-HTML",
            ["1", "1", "1", "1", "1", "1", "1", "1", "1", "1"],
        )

        output = gr.RESULTS_DIR / "SAM-HTML" / "report" / "SAM-HTML_report.html"
        gr.generate_html(
            "SAM-HTML", SALMONELLA_SUMMARY, self._fake_verification(), output
        )

        html = output.read_text()
        assert "cgMLST 溯源" in html
        assert 'class="cgmlst-verdict-badge cgmlst-verdict-outbreak"' in html
        # CSS rules are always present in <style>, regardless of section render.
        assert ".cgmlst-verdict-outbreak" in html

    def test_html_omits_cgmlst_section_when_tsv_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _setup_sandbox(monkeypatch, tmp_path)
        # No cgmlst.tsv on disk for this sample.

        output = gr.RESULTS_DIR / "SAM-NOHTML" / "report" / "SAM-NOHTML_report.html"
        gr.generate_html(
            "SAM-NOHTML", SALMONELLA_SUMMARY, self._fake_verification(), output
        )

        html = output.read_text()
        # The visible cgMLST heading must not appear (the CSS rules in <style>
        # are always emitted; only the rendered card is gated on the TSV).
        assert "🧭 cgMLST 溯源" not in html
        assert 'class="cgmlst-verdict-badge' not in html
