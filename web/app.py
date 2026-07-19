"""FastAPI backend for hermes-bacmap Web UI.

Run: uvicorn web.app:app --reload --port 8080
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.config import RESULTS_DIR as _RESULTS_DIR, DB_PATH as _DB_PATH
from hermes_bacmap.services.sample_summary import (
    read_summary,
    sample_status,
    snp_cohort_status,
    summary_fields,
)

_WORKFLOW_DIR = _PROJECT_ROOT / "workflows" / "bacmap"
_SAMPLES_TSV = _WORKFLOW_DIR / "config" / "samples.tsv"

app = FastAPI(title="Hermes-bacmap", version="0.5.0")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def _read_samples_tsv() -> list[dict]:
    if not _SAMPLES_TSV.exists():
        return []
    with _SAMPLES_TSV.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _get_annotation(sample_id: str) -> dict | None:
    p = _RESULTS_DIR / sample_id / "annotation" / "annotation.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


@app.get("/api/samples")
def list_samples() -> dict:
    samples = []
    for row in _read_samples_tsv():
        sid = row.get("sample", "")
        fields = summary_fields(read_summary(_RESULTS_DIR, sid) or {})

        samples.append(
            {
                "sample_id": sid,
                "species_configured": row.get("species", ""),
                "species_detected": fields["species"],
                "mlst_st": fields["mlst_st"],
                "serotype": fields["serotype"],
                "status": sample_status(_RESULTS_DIR, sid),
            }
        )

    snp_summary = snp_cohort_status(_RESULTS_DIR)["summary"]
    return {"samples": samples, "snp_cohort": {"summary": snp_summary}}


@app.get("/api/samples/{sample_id}")
def get_sample(sample_id: str) -> dict:
    summary = read_summary(_RESULTS_DIR, sample_id)
    if not summary:
        return JSONResponse({"error": f"Sample {sample_id} not found"}, status_code=404)
    return summary


@app.get("/api/samples/{sample_id}/annotation")
def get_annotation(sample_id: str) -> dict:
    ann = _get_annotation(sample_id)
    if not ann:
        return JSONResponse({"error": f"Annotation for {sample_id} not found"}, status_code=404)
    return ann


@app.get("/api/snp")
def get_snp_tree() -> dict:
    p = _RESULTS_DIR / "snp" / "snp_summary.json"
    if not p.exists():
        return JSONResponse({"error": "SNP tree not available"}, status_code=404)
    return json.loads(p.read_text())


@app.get("/api/search")
def search_samples(q: str = Query(..., description="Search query")) -> dict:
    from hermes_bacmap.tools import search_samples as _do_search

    result = _do_search({"query": q})
    return json.loads(result)


@app.get("/api/status")
def pipeline_status() -> dict:
    samples = _read_samples_tsv()
    statuses = [sample_status(_RESULTS_DIR, r.get("sample", "")) for r in samples]
    return {
        "total_samples": len(samples),
        "completed": statuses.count("completed"),
        "in_progress": statuses.count("in-progress"),
        "not_started": statuses.count("not-started"),
        "snp_available": snp_cohort_status(_RESULTS_DIR)["summary"],
    }


@app.get("/api/metadata")
def get_metadata(
    strain_id: str = "",
    province: str = "",
    outbreak_id: str = "",
    sample_source: str = "",
    isolation_date_from: str = "",
    isolation_date_to: str = "",
) -> dict:
    from hermes_bacmap.services.strain_metadata import StrainMetadataService

    db = _DB_PATH
    with StrainMetadataService(db) as svc:
        if strain_id:
            meta = svc.get(strain_id)
            if not meta:
                return JSONResponse({"error": f"Strain {strain_id} not found"}, status_code=404)
            return meta.to_dict()

        search_kwargs: dict = {}
        if province:
            search_kwargs["province"] = province
        if outbreak_id:
            search_kwargs["outbreak_id"] = outbreak_id
        if sample_source:
            search_kwargs["sample_source"] = sample_source
        if isolation_date_from:
            search_kwargs["isolation_date_from"] = isolation_date_from
        if isolation_date_to:
            search_kwargs["isolation_date_to"] = isolation_date_to

        results = svc.search(**search_kwargs) if search_kwargs else svc.list_all()
        return {"count": len(results), "results": [m.to_dict() for m in results]}


@app.get("/api/lab-results")
def get_lab_results(sample_id: str = "", category: str = "") -> dict:
    from hermes_bacmap.services.lab_results import LabResultService

    db = _DB_PATH
    with LabResultService(db) as svc:
        if sample_id:
            results = svc.get_by_strain(sample_id, category=category or None)
        elif category:
            results = svc.search(category=category)
        else:
            results = svc.search(limit=200)
        return {"count": len(results), "results": [r.to_dict() for r in results]}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (Path(__file__).parent / "templates" / "index.html").read_text()
