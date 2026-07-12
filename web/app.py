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

_RESULTS_DIR = _PROJECT_ROOT / "results"
_WORKFLOW_DIR = _PROJECT_ROOT / "workflows" / "salmonella"
_SAMPLES_TSV = _WORKFLOW_DIR / "config" / "samples.tsv"

app = FastAPI(title="Hermes-bacmap", version="0.5.0")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def _read_samples_tsv() -> list[dict]:
    if not _SAMPLES_TSV.exists():
        return []
    with _SAMPLES_TSV.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _get_summary(sample_id: str) -> dict | None:
    p = _RESULTS_DIR / sample_id / "report" / f"{sample_id}_summary.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


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
        summary = _get_summary(sid)
        contigs = _RESULTS_DIR / sid / "assembly" / "contigs.fasta"

        if summary:
            status = "completed"
        elif contigs.exists():
            status = "in-progress"
        else:
            status = "not-started"

        steps_data = summary.get("steps", {}) if summary else {}
        species = steps_data.get("species", {})
        species_name = species.get("species", "N/A") if isinstance(species, dict) else str(species)

        mlst_raw = steps_data.get("mlst", "")
        st = "N/A"
        if mlst_raw and isinstance(mlst_raw, str):
            parts = mlst_raw.strip().split("\t")
            if len(parts) >= 2:
                st = parts[-1]

        sero = steps_data.get("serotype", {})
        serotype = sero.get("sistr", "N/A") if isinstance(sero, dict) else "N/A"

        samples.append({
            "sample_id": sid,
            "species_configured": row.get("species", ""),
            "species_detected": species_name,
            "mlst_st": st,
            "serotype": serotype,
            "status": status,
        })

    snp_tree = _RESULTS_DIR / "snp" / "snp_summary.json"
    snp_status = snp_tree.exists()

    return {"samples": samples, "snp_cohort": {"summary": snp_status}}


@app.get("/api/samples/{sample_id}")
def get_sample(sample_id: str) -> dict:
    summary = _get_summary(sample_id)
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
    done = sum(1 for r in samples if _get_summary(r.get("sample", "")))
    total = len(samples)
    snp_p = _RESULTS_DIR / "snp" / "snp_summary.json"
    return {
        "total_samples": total,
        "completed": done,
        "in_progress": sum(
            1 for r in samples
            if (_RESULTS_DIR / r.get("sample", "") / "assembly" / "contigs.fasta").exists()
            and not _get_summary(r.get("sample", ""))
        ),
        "not_started": total - done - sum(
            1 for r in samples
            if (_RESULTS_DIR / r.get("sample", "") / "assembly" / "contigs.fasta").exists()
            and not _get_summary(r.get("sample", ""))
        ),
        "snp_available": snp_p.exists(),
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
    from hermes_bacmap.strain_metadata import StrainMetadataService

    db = _PROJECT_ROOT / "data" / "hermes_bacmap.sqlite"
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
    from hermes_bacmap.lab_results import LabResultService

    db = _PROJECT_ROOT / "data" / "hermes_bacmap.sqlite"
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
