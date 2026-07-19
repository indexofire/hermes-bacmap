"""High-level analysis pipeline tool handlers (project.md §7).

Covers bio_analyze_pathogen, bio_get_result, bio_verify_result,
bio_generate_report, bio_list_samples, bio_gene_scan, bio_vpa_serotype,
bio_validate_taxonomy, bio_annotate, bio_diagnose. All handlers return JSON
strings. Errors are {"error": "..."}.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hermes_bacmap.utils import parse_mlst

from ._common import (
    _PROJECT_ROOT,
    _RESULTS_DIR,
    _run_project_script,
    logger,
    tool_handler,
)


@tool_handler
def analyze_pathogen(args: dict[str, Any], **kwargs: Any) -> str:
    """Trigger full analysis pipeline via Snakemake.
    Works for Salmonella, DEC, Shigella, EIEC — species routing is automatic
    via three-gene identification (invA/uidA/ipaH)."""
    sample_id = args.get("sample_id", "")
    cores = args.get("cores", 8)

    _run_project_script("run_analysis.py", ["--sample", sample_id, "--cores", str(cores)])

    summary_path = _RESULTS_DIR / sample_id / "report" / f"{sample_id}_summary.json"
    if summary_path.exists():
        with summary_path.open() as f:
            return str(f.read())
    return json.dumps({"error": "Pipeline completed but summary not found"})


@tool_handler
def get_result(args: dict[str, Any], **kwargs: Any) -> str:
    """Retrieve analysis summary for a completed sample."""
    sample_id = args.get("sample_id", "")
    summary_path = _RESULTS_DIR / sample_id / "report" / f"{sample_id}_summary.json"

    if not summary_path.exists():
        return json.dumps(
            {"error": f"No results found for {sample_id}. Run bio_analyze_pathogen first."}
        )

    with summary_path.open() as f:
        summary = json.load(f)

    steps = summary.get("steps", {})

    sp = steps.get("species", {})
    verdict = sp.get("verdict", "N/A") if isinstance(sp, dict) else str(sp)

    mlst_raw = steps.get("mlst", "")
    st = parse_mlst(mlst_raw)["st"] if mlst_raw else "N/A"

    sero = steps.get("serotype", {})
    serovar = sero.get("sistr", "N/A") if isinstance(sero, dict) else "N/A"

    amr = steps.get("amr", {})
    card = amr.get("abricate_card", []) if isinstance(amr, dict) else []
    vfdb = amr.get("abricate_vfdb", []) if isinstance(amr, dict) else []
    pl = steps.get("plasmid", {}).get("plasmidfinder", [])

    dec = steps.get("dec", {}) if isinstance(steps.get("dec", {}), dict) else {}
    ipah = dec.get("ipaH", "N/A")
    pathotype = dec.get("pathotype", "N/A")

    species_type = "unknown"
    if verdict == "Salmonella":
        species_type = "Salmonella"
    elif "positive" in str(ipah):
        species_type = "Shigella/EIEC"
    elif "not_Salmonella" in verdict:
        species_type = "E. coli/DEC"

    pt_line = "N/A"
    if pathotype and pathotype != "N/A":
        pt_lines = pathotype.strip().split("\n")
        if len(pt_lines) >= 2:
            pt_line = pt_lines[-1].split("\t")[0]

    compact = {
        "sample_id": sample_id,
        "species_type": species_type,
        "species_verdict": verdict,
        "mlst_st": st,
        "serotype": serovar,
        "ipaH": ipah,
        "pathotype": pt_line,
        "amr_genes_count": len(card),
        "virulence_genes_count": len(vfdb),
        "plasmid_count": len(pl),
        "report_path": str(summary_path),
    }
    return json.dumps(compact, ensure_ascii=False)


@tool_handler
def verify_result(args: dict[str, Any], **kwargs: Any) -> str:
    """Run Deterministic Verifier on a sample's results."""
    sample_id = args.get("sample_id", "")
    summary_path = _RESULTS_DIR / sample_id / "report" / f"{sample_id}_summary.json"

    if not summary_path.exists():
        return json.dumps({"error": f"No results for {sample_id}"})

    with summary_path.open() as f:
        summary = json.load(f)

    try:
        from hermes_bacmap.analysis.deterministic_verifier import DeterministicVerifier

        v = DeterministicVerifier()
        result = v.verify_all(summary)
        return json.dumps(
            {
                "passed": result.passed,
                "failed_count": result.failed_count,
                "needs_human_review": result.needs_human_review,
                "checks": [
                    {"name": c.name, "passed": c.passed, "message": c.message}
                    for c in result.checks
                ],
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("verify_result failed")
        return json.dumps({"error": f"Verifier failed: {e}"})


@tool_handler
def generate_report(args: dict[str, Any], **kwargs: Any) -> str:
    """Generate HTML report for a sample."""
    sample_id = args.get("sample_id", "")
    _run_project_script("generate_report.py", ["--sample", sample_id], timeout=60)
    report_path = _RESULTS_DIR / sample_id / "report" / f"{sample_id}_report.html"
    if report_path.exists():
        return json.dumps({"sample_id": sample_id, "report_path": str(report_path)})
    return json.dumps({"error": "Report generation failed"})


@tool_handler
def list_samples(args: dict[str, Any], **kwargs: Any) -> str:
    """List all samples and their analysis status."""
    import csv

    samples_tsv = _PROJECT_ROOT / "workflows/bacmap/config/samples.tsv"
    if not samples_tsv.exists():
        return json.dumps({"error": "samples.tsv not found"})

    status_list = []
    with samples_tsv.open() as f:
        for r in csv.DictReader(f, delimiter="\t"):
            sid = r["sample"]
            summary = _RESULTS_DIR / sid / "report" / f"{sid}_summary.json"
            contigs = _RESULTS_DIR / sid / "assembly" / "contigs.fasta"

            if summary.exists():
                status = "completed"
            elif contigs.exists():
                status = "in-progress"
            else:
                status = "not-started"

            status_list.append(
                {"sample_id": sid, "species": r.get("species", ""), "status": status}
            )

    return json.dumps({"samples": status_list}, ensure_ascii=False)


@tool_handler
def gene_scan(args: dict[str, Any], **kwargs: Any) -> str:
    """Scan contigs against gene database(s). Returns JSON."""
    contigs_path = args.get("contigs_path", "")
    database = args.get("database", "card")
    min_identity = args.get("min_identity", 80.0)
    min_coverage = args.get("min_coverage", 80.0)

    contigs = Path(contigs_path)
    if not contigs.exists():
        return json.dumps({"error": f"Contigs not found: {contigs_path}"})

    db_list = [d.strip() for d in database.split(",")]

    try:
        from hermes_bacmap.analysis.gene_scanner import scan, scan_multi

        if len(db_list) == 1:
            result = scan(
                contigs,
                db_name=db_list[0],
                min_identity=min_identity,
                min_coverage=min_coverage,
            )
            return json.dumps(result.to_dict(), ensure_ascii=False)
        else:
            results = scan_multi(
                contigs,
                db_list,
                min_identity=min_identity,
                min_coverage=min_coverage,
            )
            output = {name: r.to_dict() for name, r in results.items()}
            return json.dumps(output, ensure_ascii=False)
    except FileNotFoundError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        logger.exception("gene_scan failed")
        return json.dumps({"error": f"gene_scan failed: {e}"})


@tool_handler
def vpa_serotype(args: dict[str, Any], **kwargs: Any) -> str:
    """Predict V. parahaemolyticus O/K serotype from contigs."""
    contigs_path = args.get("contigs_path", "")
    sample_id = args.get("sample_id", "")

    contigs = Path(contigs_path)
    if not contigs.exists():
        return json.dumps({"error": f"Contigs not found: {contigs_path}"})

    if not sample_id:
        sample_id = contigs.parent.parent.name

    try:
        from hermes_bacmap.typing.vpa_serotyper import VpaSerotyper

        serotyper = VpaSerotyper()
        result = serotyper.analyze(contigs_path, sample_id)
        return json.dumps(result.to_dict(), ensure_ascii=False)
    except Exception as e:
        logger.exception("vpa_serotype failed")
        return json.dumps({"error": f"VPA serotyping failed: {e}"})


@tool_handler
def validate_taxonomy(args: dict[str, Any], **kwargs: Any) -> str:
    """Validate genome taxonomy — simple (marker genes) or standard (CheckM2 + GTDB-Tk)."""
    sample_id = args.get("sample_id", "")
    mode = args.get("mode", "simple")

    contigs = _RESULTS_DIR / sample_id / "assembly" / "contigs.fasta"
    if not contigs.exists():
        return json.dumps({"error": f"Contigs not found for {sample_id}. Run analysis first."})

    try:
        from hermes_bacmap.analysis.taxonomic_validator import validate_genome

        output_dir = _RESULTS_DIR / sample_id / "taxonomy"
        result = validate_genome(contigs, mode=mode, output_dir=output_dir)
        return json.dumps(result.to_dict(), ensure_ascii=False)
    except Exception as e:
        logger.exception("validate_taxonomy failed")
        return json.dumps({"error": f"Taxonomy validation failed: {e}"})


@tool_handler
def annotate_genome(args: dict[str, Any], **kwargs: Any) -> str:
    """Annotate assembled contigs with pyrodigal + Prokka DBs."""
    contigs_path = args.get("contigs_path", "")
    sample_id = args.get("sample_id", "")
    output_path = args.get("output_path", "")

    contigs = Path(contigs_path)
    if not contigs.exists():
        return json.dumps({"error": f"Contigs not found: {contigs_path}"})

    if not sample_id:
        sample_id = contigs.parent.parent.name

    if not output_path:
        output_path = str(_RESULTS_DIR / sample_id / "annotation" / "annotation.json")

    try:
        from hermes_bacmap.analysis.genome_annotator import annotate

        result = annotate(contigs_path, sample_id)
        result.save(output_path)

        summary = result.summary
        return json.dumps(
            {
                "sample_id": sample_id,
                "output": output_path,
                "summary": summary,
                "top_genes": [
                    {
                        "gene": f.gene,
                        "product": f.product,
                        "identity": f.identity,
                        "source": f.source,
                    }
                    for f in result.features
                    if f.gene and f.identity >= 80
                ][:20],
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("annotate_genome failed")
        return json.dumps({"error": f"Annotation failed: {e}"})


@tool_handler
def diagnose_failure(args: dict[str, Any], **kwargs: Any) -> str:
    """Diagnose pipeline failure from Snakemake log or stderr text."""
    from hermes_bacmap.analysis.failure_diagnostics import diagnose, diagnose_from_log

    stderr_text = args.get("stderr_text", "")
    log_path = args.get("log_path", "")

    if stderr_text:
        result = diagnose(stderr_text)
    elif log_path:
        result = diagnose_from_log(log_path)
    else:
        result = diagnose_from_log(str(_PROJECT_ROOT / "workflows/bacmap/.snakemake/log"))

    return json.dumps(result.to_dict(), ensure_ascii=False)
