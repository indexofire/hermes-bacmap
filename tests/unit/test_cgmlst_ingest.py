"""Tests for per-sample cgMLST profile ingestion into GOM (plan todo 4).

Mirrors the fixture + assertion style of tests/unit/test_cohort_ingest.py and
tests/unit/test_cgmlst_gom_schema.py. The ingest logic lives in the
``scripts/ingest_results.py`` script module, so we import it via sys.path
(same pattern as tests/unit/test_sample_name_validation.py:12).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import ingest_results  # noqa: E402

from hermes_bacmap.services.genome_object_service import (  # noqa: E402
    GenomeObjectService,
    ObjectType,
)

CGMLST_PIPELINE_VERSION = "cgmlst-pipeline-v0.1"

# A single-row TSV exercising every gmlst marker (23 / 23* / ~5 / 15? / 1,2 / -).
# Expected parse: n_called=2 (SE-1, SE-2), novel=[SE-3], missing=[SE-4, SE-6],
# ambiguous=[SE-5], n_total=6.
HAPPY_TSV = (
    "File\tScheme\tST\tSE-1\tSE-2\tSE-3\tSE-4\tSE-5\tSE-6\n"
    "SAM-TYP-001\tsenterica_2\t-\t23\t23*\t~5\t15?\t1,2\t-"
)

# gmlst-binary-unavailable fallback (typing_amr.smk pattern) — scheme present
# but zero loci. Ingest must skip gracefully rather than build an empty profile.
FALLBACK_NA_TSV = "File\tScheme\tST\nSAM-TYP-001\tsenterica_2\tN/A"


def _write_cgmlst_tsv(results_root: Path, sample_id: str, content: str) -> Path:
    cgmlst_path = results_root / sample_id / "typing" / "cgmlst.tsv"
    cgmlst_path.parent.mkdir(parents=True, exist_ok=True)
    cgmlst_path.write_text(content)
    return cgmlst_path


def _list_cgmlst_profile_objs(gos: GenomeObjectService, strain_id: str) -> list[Any]:
    return [
        o
        for o in gos.list_by_type(ObjectType.ANALYSIS)
        if o.strain_id == strain_id and o.payload.get("analysis_type") == "cgmlst_profile"
    ]


class TestIngestSampleCgmlstHappyPath:
    def test_ingest_creates_queryable_versioned_object(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")
        _write_cgmlst_tsv(tmp_path, "SAM-TYP-001", HAPPY_TSV)

        with GenomeObjectService(tmp_db_path) as gos:
            oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")

            assert oid is not None
            objs = _list_cgmlst_profile_objs(gos, "SAM-TYP-001")
            assert len(objs) == 1
            obj = objs[0]
            assert obj.object_id == oid
            assert obj.version == 1
            assert obj.pipeline_version == CGMLST_PIPELINE_VERSION
            assert obj.created_by == "cgmlst-pipeline"
            assert obj.organism == "Salmonella enterica"
            assert obj.payload["analysis_type"] == "cgmlst_profile"
            assert obj.payload["scheme"] == "senterica_2"
            assert obj.payload["n_loci"] == 6
            assert obj.payload["n_called"] == 2
            assert obj.payload["n_total"] == 6
            assert obj.payload["alleles"]["SE-1"] == 23
            assert obj.payload["alleles"]["SE-2"] == 23
            assert obj.payload["alleles"]["SE-3"] is None
            assert obj.payload["novel_loci"] == ["SE-3"]
            assert obj.payload["ambiguous_loci"] == ["SE-5"]
            assert sorted(obj.payload["missing_loci"]) == ["SE-4", "SE-6"]
            assert obj.database_versions["gmlst"] == "0.1.1"
            assert (
                obj.database_versions["cgmlst_scheme"]
                == "senterica_2@unversioned"
            )

    def test_rerun_same_content_skips_no_duplicate(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")
        _write_cgmlst_tsv(tmp_path, "SAM-TYP-001", HAPPY_TSV)

        with GenomeObjectService(tmp_db_path) as gos:
            first_oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")
            second_oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")

            assert first_oid == second_oid
            objs = _list_cgmlst_profile_objs(gos, "SAM-TYP-001")
            assert len(objs) == 1
            assert gos.get_latest_version(first_oid) == 1

    def test_meta_hash_change_creates_new_version(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_dir = tmp_path / "ref"
        monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", ref_dir)
        _write_cgmlst_tsv(tmp_path, "SAM-TYP-001", HAPPY_TSV)

        with GenomeObjectService(tmp_db_path) as gos:
            first_oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")
            assert gos.get_latest_version(first_oid) == 1

            scheme_meta_dir = ref_dir / "senterica_2"
            scheme_meta_dir.mkdir(parents=True)
            (scheme_meta_dir / ".meta.json").write_text('{"version": "v1"}')

            second_oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")
            assert second_oid == first_oid
            assert gos.get_latest_version(first_oid) == 2

            v2 = gos.read(first_oid, 2)
            assert v2.database_versions["cgmlst_scheme"] != "senterica_2@unversioned"
            assert v2.database_versions["cgmlst_scheme"].startswith("senterica_2@")

    def test_mlst_finished_event_logged(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")
        _write_cgmlst_tsv(tmp_path, "SAM-TYP-001", HAPPY_TSV)

        with GenomeObjectService(tmp_db_path) as gos:
            oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")
            events = gos.list_events(oid)
            mlst_events = [e for e in events if e.event_type == "mlst_finished"]
            assert len(mlst_events) == 1
            assert mlst_events[0].event_payload["scheme"] == "senterica_2"
            assert mlst_events[0].event_payload["n_called"] == 2

    def test_file_artifact_registered(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")
        _write_cgmlst_tsv(tmp_path, "SAM-TYP-001", HAPPY_TSV)

        with GenomeObjectService(tmp_db_path) as gos:
            oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")
            artifacts = gos.list_file_artifacts(oid, 1)
            assert len(artifacts) == 1
            assert artifacts[0].file_type == "cgmlst_profile"


class TestIngestSampleCgmlstGracefulSkip:
    def test_missing_cgmlst_tsv_returns_none(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")

        with GenomeObjectService(tmp_db_path) as gos:
            oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")

            assert oid is None
            assert _list_cgmlst_profile_objs(gos, "SAM-TYP-001") == []

    def test_fallback_na_tsv_skipped(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")
        _write_cgmlst_tsv(tmp_path, "SAM-TYP-001", FALLBACK_NA_TSV)

        with GenomeObjectService(tmp_db_path) as gos:
            oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")

            assert oid is None
            assert _list_cgmlst_profile_objs(gos, "SAM-TYP-001") == []


class TestIngestSampleCgmlstMalformed:
    def test_multisample_tsv_value_error_caught(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")
        multisample = (
            "File\tScheme\tST\tSE-1\tSE-2\n"
            "SAM-A\tsenterica_2\t-\t1\t2\n"
            "SAM-B\tsenterica_2\t-\t3\t4"
        )
        _write_cgmlst_tsv(tmp_path, "SAM-TYP-001", multisample)

        with GenomeObjectService(tmp_db_path) as gos:
            oid = ingest_results._ingest_sample_cgmlst(gos, "SAM-TYP-001")

            assert oid is None
            assert _list_cgmlst_profile_objs(gos, "SAM-TYP-001") == []


class TestIngestCgmlstLoop:
    def test_loops_all_samples_in_samples_tsv(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")
        monkeypatch.setattr(ingest_results, "ROOT", tmp_path)

        config_dir = tmp_path / "workflows" / "bacmap" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "samples.tsv").write_text(
            "sample\tspecies\nSAM-A\tSalmonella\nSAM-B\tSalmonella\n"
        )
        _write_cgmlst_tsv(
            tmp_path,
            "SAM-A",
            "File\tScheme\tST\tL1\tL2\nSAM-A\tsenterica_2\t-\t1\t2",
        )
        _write_cgmlst_tsv(
            tmp_path,
            "SAM-B",
            "File\tScheme\tST\tL1\tL2\nSAM-B\tsenterica_2\t-\t3\t4",
        )

        with GenomeObjectService(tmp_db_path) as gos:
            oids = ingest_results.ingest_cgmlst(gos)

            assert len(oids) == 2
            assert _list_cgmlst_profile_objs(gos, "SAM-A") != []
            assert _list_cgmlst_profile_objs(gos, "SAM-B") != []

    def test_no_samples_tsv_returns_empty(
        self, tmp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "ROOT", tmp_path)

        with GenomeObjectService(tmp_db_path) as gos:
            oids = ingest_results.ingest_cgmlst(gos)
            assert oids == []


class TestCgmlstMetaHash:
    def test_missing_scheme_returns_unversioned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")
        assert ingest_results._cgmlst_meta_hash("senterica_2") == "unversioned"

    def test_empty_scheme_returns_unversioned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", tmp_path / "ref")
        assert ingest_results._cgmlst_meta_hash("") == "unversioned"

    def test_existing_meta_json_returns_12_char_hash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ref_dir = tmp_path / "ref"
        scheme_dir = ref_dir / "senterica_2"
        scheme_dir.mkdir(parents=True)
        (scheme_dir / ".meta.json").write_text('{"version": "v1"}')
        monkeypatch.setattr(ingest_results, "CGMLST_REFERENCE_DIR", ref_dir)

        h = ingest_results._cgmlst_meta_hash("senterica_2")
        assert len(h) == 12
        assert all(c in "0123456789abcdef" for c in h)
