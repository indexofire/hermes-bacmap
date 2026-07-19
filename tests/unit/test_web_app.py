"""Smoke tests for the FastAPI web UI (web/app.py).

Uses Starlette TestClient against tmp results/db paths; no real pipeline
artifacts required. Requires the `web` extra (fastapi + httpx).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="web extra not installed")
pytest.importorskip("httpx", reason="web extra not installed")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import web.app as web_app  # noqa: E402
from web.app import app  # noqa: E402

_SAMPLES_TSV = "sample\tspecies\nDONE\tSalmonella\nWIP\tSalmonella\nNEW\tShigella\n"


@pytest.fixture
def client(tmp_path, monkeypatch):
    results = tmp_path / "results"

    summary = results / "DONE" / "report" / "DONE_summary.json"
    summary.parent.mkdir(parents=True)
    summary.write_text(
        json.dumps(
            {
                "sample": "DONE",
                "steps": {
                    "species": {"species": "Salmonella"},
                    "mlst": "ST\trpoB\n19\t12\n",
                    "serotype": {"sistr": "Typhimurium"},
                },
            }
        )
    )
    contigs = results / "WIP" / "assembly" / "contigs.fasta"
    contigs.parent.mkdir(parents=True)
    contigs.write_text(">c1\nATGC\n")

    tsv = tmp_path / "samples.tsv"
    tsv.write_text(_SAMPLES_TSV)

    monkeypatch.setattr(web_app, "_RESULTS_DIR", results)
    monkeypatch.setattr(web_app, "_SAMPLES_TSV", tsv)
    monkeypatch.setattr(web_app, "_DB_PATH", tmp_path / "test.sqlite")
    return TestClient(app)


class TestSamples:
    def test_list_samples_status_and_fields(self, client):
        r = client.get("/api/samples")
        assert r.status_code == 200
        data = r.json()
        by_id = {s["sample_id"]: s for s in data["samples"]}
        assert by_id["DONE"]["status"] == "completed"
        assert by_id["DONE"]["species_detected"] == "Salmonella"
        assert by_id["DONE"]["mlst_st"] == "19"
        assert by_id["DONE"]["serotype"] == "Typhimurium"
        assert by_id["WIP"]["status"] == "in-progress"
        assert by_id["NEW"]["status"] == "not-started"
        assert by_id["NEW"]["species_detected"] == "N/A"
        assert data["snp_cohort"] == {"summary": False}

    def test_get_sample(self, client):
        r = client.get("/api/samples/DONE")
        assert r.status_code == 200
        assert r.json()["sample"] == "DONE"

    def test_get_sample_404(self, client):
        r = client.get("/api/samples/NOPE")
        assert r.status_code == 404

    def test_annotation_404(self, client):
        r = client.get("/api/samples/DONE/annotation")
        assert r.status_code == 404

    def test_annotation_ok(self, client, tmp_path):
        ann = tmp_path / "results" / "DONE" / "annotation" / "annotation.json"
        ann.parent.mkdir(parents=True)
        ann.write_text(json.dumps({"features": 42}))
        r = client.get("/api/samples/DONE/annotation")
        assert r.status_code == 200
        assert r.json()["features"] == 42


class TestStatusAndSnp:
    def test_pipeline_status(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        assert r.json() == {
            "total_samples": 3,
            "completed": 1,
            "in_progress": 1,
            "not_started": 1,
            "snp_available": False,
        }

    def test_snp_404(self, client):
        r = client.get("/api/snp")
        assert r.status_code == 404

    def test_snp_ok(self, client, tmp_path):
        snp = tmp_path / "results" / "snp" / "snp_summary.json"
        snp.parent.mkdir(parents=True)
        snp.write_text(json.dumps({"n_sites": 123}))
        r = client.get("/api/snp")
        assert r.status_code == 200
        assert r.json()["n_sites"] == 123


class TestSearch:
    def test_search_delegates_to_tool(self, client, monkeypatch):
        import hermes_bacmap.tools

        monkeypatch.setattr(
            hermes_bacmap.tools,
            "search_samples",
            lambda args: json.dumps({"echo": args["query"]}),
        )
        r = client.get("/api/search", params={"q": "Typhimurium"})
        assert r.status_code == 200
        assert r.json() == {"echo": "Typhimurium"}


class TestDbRoutes:
    def test_metadata_empty_db(self, client):
        r = client.get("/api/metadata")
        assert r.status_code == 200
        assert r.json() == {"count": 0, "results": []}

    def test_metadata_strain_not_found(self, client):
        r = client.get("/api/metadata", params={"strain_id": "NOPE"})
        assert r.status_code == 404

    def test_lab_results_empty_db(self, client):
        r = client.get("/api/lab-results")
        assert r.status_code == 200
        assert r.json() == {"count": 0, "results": []}


class TestIndex:
    def test_index_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
