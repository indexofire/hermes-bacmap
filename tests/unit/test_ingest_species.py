"""Species identification ingestion into GOM (species-id P0)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

_SPEC = importlib.util.spec_from_file_location(
    "ingest_results", _PROJECT_ROOT / "scripts" / "ingest_results.py"
)
ingest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ingest)

from hermes_bacmap.services.genome_object_service import (  # noqa: E402
    GenomeObjectService,
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(ingest, "RESULTS_DIR", results)
    markers = tmp_path / "markers.fasta"
    markers.write_bytes(b">x\nACGT\n")
    monkeypatch.setattr(ingest, "_markers_db_version", lambda: "feedface")
    return results


def _write_species_json(results: Path, sample: str, payload: dict) -> Path:
    p = results / sample / "species"
    p.mkdir(parents=True, exist_ok=True)
    out = p / "species_id.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


def _gos(tmp_path):
    return GenomeObjectService(tmp_path / "gom.sqlite")


_MODERN = {
    "species": "Salmonella",
    "confidence": "high",
    "method": "marker",
    "database": {"name": "species_markers", "version": "abcd1234"},
    "detected_markers": [{"gene": "invA", "identity": 99.0, "coverage": 100.0}],
    "interpretation": "x",
}


class TestIngestSampleSpecies:
    def test_ingests_modern_json(self, tmp_path, env):
        _write_species_json(env, "SAM-1", _MODERN)
        with _gos(tmp_path) as gos:
            oid = ingest._ingest_sample_species(gos, "SAM-1")
            assert oid
            objs = gos.list_species_identifications("SAM-1")
            assert len(objs) == 1
            payload = objs[0].payload
            assert payload["method"] == "marker"
            assert payload["database"] == {"name": "species_markers", "version": "abcd1234"}
            assert payload["result"]["species"] == "Salmonella"
            assert objs[0].database_signature == "species_markers@abcd1234"
            events = gos.list_events(oid)
            assert any(e.event_type == "species_identified" for e in events)

    def test_idempotent_same_method_and_signature(self, tmp_path, env):
        _write_species_json(env, "SAM-1", _MODERN)
        with _gos(tmp_path) as gos:
            first = ingest._ingest_sample_species(gos, "SAM-1")
            second = ingest._ingest_sample_species(gos, "SAM-1")
            assert second == first
            assert len(gos.list_species_identifications("SAM-1")) == 1

    def test_new_database_version_creates_new_object(self, tmp_path, env):
        _write_species_json(env, "SAM-1", _MODERN)
        updated = dict(_MODERN)
        updated["database"] = {"name": "species_markers", "version": "deadbeef"}
        with _gos(tmp_path) as gos:
            ingest._ingest_sample_species(gos, "SAM-1")
            _write_species_json(env, "SAM-1", updated)
            ingest._ingest_sample_species(gos, "SAM-1")
            objs = gos.list_species_identifications("SAM-1")
            assert len(objs) == 2

    def test_two_methods_coexist(self, tmp_path, env):
        _write_species_json(env, "SAM-1", _MODERN)
        ani = dict(_MODERN)
        ani["method"] = "skani_gtdb"
        ani["database"] = {"name": "skani_gtdb_r226", "version": "R226"}
        with _gos(tmp_path) as gos:
            ingest._ingest_sample_species(gos, "SAM-1")
            _write_species_json(env, "SAM-1", ani)
            ingest._ingest_sample_species(gos, "SAM-1")
            methods = sorted(o.payload["method"] for o in gos.list_species_identifications("SAM-1"))
            assert methods == ["marker", "skani_gtdb"]

    def test_legacy_json_gets_marker_method_and_version(self, tmp_path, env):
        legacy = {"species": "DEC", "confidence": "high", "detected_markers": []}
        _write_species_json(env, "SAM-2", legacy)
        with _gos(tmp_path) as gos:
            ingest._ingest_sample_species(gos, "SAM-2")
            objs = gos.list_species_identifications("SAM-2")
            assert len(objs) == 1
            assert objs[0].payload["method"] == "marker"
            assert objs[0].payload["database"]["version"] == "feedface"

    def test_missing_json_returns_none(self, tmp_path, env):
        with _gos(tmp_path) as gos:
            assert ingest._ingest_sample_species(gos, "SAM-NONE") is None


class TestIngestSpeciesBulk:
    def test_scans_results_dir(self, tmp_path, env, capsys):
        _write_species_json(env, "SAM-1", _MODERN)
        _write_species_json(env, "SAM-2", dict(_MODERN, species="DEC"))
        with _gos(tmp_path) as gos:
            oids = ingest.ingest_species(gos)
        assert len(oids) == 2
