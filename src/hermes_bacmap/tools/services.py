"""Service-backed tool handlers.

Covers bio_query_metadata, bio_add_metadata, bio_query_lab_results,
bio_add_lab_result, bio_snp_tree, bio_search_samples. These talk to the
SQLite GOM database via hermes_bacmap.services (lazy imports). All handlers
return JSON strings. Errors are {"error": "..."}.
"""

from __future__ import annotations

import json
from typing import Any

from hermes_bacmap.utils import parse_mlst

from ._common import (
    _DEFAULT_DB_PATH,
    _RESULTS_DIR,
    logger,
    tool_handler,
)


@tool_handler
def query_metadata(args: dict[str, Any], **kwargs: Any) -> str:
    """Query strain background metadata."""
    db_path = _DEFAULT_DB_PATH
    if not db_path.exists():
        return json.dumps({"error": "Database not found. Run analysis first."})

    try:
        from hermes_bacmap.services.strain_metadata import StrainMetadataService

        strain_id = args.get("strain_id")
        search_kwargs = {}
        for key in (
            "province",
            "outbreak_id",
            "sample_source",
            "isolation_date_from",
            "isolation_date_to",
        ):
            val = args.get(key)
            if val:
                search_kwargs[key] = val

        with StrainMetadataService(db_path) as svc:
            if strain_id:
                meta = svc.get(strain_id)
                if not meta:
                    return json.dumps({"error": f"Strain {strain_id} not found"})
                return json.dumps(meta.to_dict(), ensure_ascii=False)
            else:
                results = svc.search(**search_kwargs) if search_kwargs else svc.list_all()
                return json.dumps(
                    {"count": len(results), "results": [m.to_dict() for m in results]},
                    ensure_ascii=False,
                )
    except Exception as e:
        logger.exception("query_metadata failed")
        return json.dumps({"error": f"Query failed: {e}"})


@tool_handler
def add_metadata(args: dict[str, Any], **kwargs: Any) -> str:
    """Add or update strain background metadata."""
    strain_id = args.get("strain_id", "")
    data = args.get("data", {})

    if not strain_id:
        return json.dumps({"error": "strain_id is required"})
    if not data or not isinstance(data, dict):
        return json.dumps({"error": "data dict is required"})

    db_path = _DEFAULT_DB_PATH

    try:
        from hermes_bacmap.services.strain_metadata import StrainMetadataService

        with StrainMetadataService(db_path) as svc:
            meta = svc.upsert(strain_id, data)
            return json.dumps(
                {
                    "strain_id": strain_id,
                    "status": "saved",
                    "data": meta.to_dict(),
                },
                ensure_ascii=False,
            )
    except Exception as e:
        logger.exception("add_metadata failed")
        return json.dumps({"error": f"Add metadata failed: {e}"})


@tool_handler
def query_lab_results(args: dict[str, Any], **kwargs: Any) -> str:
    """Query wet lab experiment results."""
    db_path = _DEFAULT_DB_PATH
    if not db_path.exists():
        return json.dumps({"error": "Database not found."})

    try:
        from hermes_bacmap.services.lab_results import LabResultService

        sample_id = args.get("sample_id", "")
        category = args.get("category", "")
        interpretation = args.get("interpretation", "")
        test_name = args.get("test_name", "")
        result = args.get("result", "")

        with LabResultService(db_path) as svc:
            if sample_id:
                results = svc.get_by_strain(sample_id, category=category or None)
            elif any([category, interpretation, test_name, result]):
                search_kwargs: dict[str, Any] = {}
                if category:
                    search_kwargs["category"] = category
                if interpretation:
                    search_kwargs["interpretation"] = interpretation
                if test_name:
                    search_kwargs["test_name"] = test_name
                if result:
                    search_kwargs["result"] = result
                results = svc.search(**search_kwargs)
            else:
                results = svc.search(limit=200)

            return json.dumps(
                {"count": len(results), "results": [r.to_dict() for r in results]},
                ensure_ascii=False,
            )
    except Exception as e:
        logger.exception("query_lab_results failed")
        return json.dumps({"error": f"Query failed: {e}"})


@tool_handler
def add_lab_result(args: dict[str, Any], **kwargs: Any) -> str:
    """Record a wet lab experiment result."""
    strain_id = args.get("strain_id", "")
    category = args.get("category", "")
    test_name = args.get("test_name", "")
    result = args.get("result", "")

    if not all([strain_id, category, test_name, result]):
        return json.dumps({"error": "strain_id, category, test_name, result are required"})

    db_path = _DEFAULT_DB_PATH

    try:
        from hermes_bacmap.services.lab_results import LabResultService

        optional = {}
        for key in (
            "interpretation",
            "method",
            "unit",
            "standard",
            "tested_date",
            "tested_by",
            "lab",
        ):
            val = args.get(key)
            if val:
                optional[key] = val

        with LabResultService(db_path) as svc:
            lr = svc.add(strain_id, category, test_name, result, **optional)
            return json.dumps(
                {
                    "status": "saved",
                    "id": lr.id,
                    "strain_id": strain_id,
                    "category": category,
                    "test_name": test_name,
                    "result": result,
                },
                ensure_ascii=False,
            )
    except Exception as e:
        logger.exception("add_lab_result failed")
        return json.dumps({"error": f"Add lab result failed: {e}"})


@tool_handler
def snp_tree(args: dict[str, Any], **kwargs: Any) -> str:
    """Retrieve cohort-level SNP phylogenetic tree and distance matrix."""
    db_path = _DEFAULT_DB_PATH
    if db_path.exists():
        try:
            from hermes_bacmap.services.genome_object_service import GenomeObjectService, ObjectType

            with GenomeObjectService(db_path) as gos:
                cohort_objs = [
                    o
                    for o in gos.list_by_type(ObjectType.ANALYSIS)
                    if o.strain_id
                    and o.strain_id.startswith("cohort:")
                    and o.strain_id.endswith("-snp")
                ]
                if cohort_objs:
                    latest = max(cohort_objs, key=lambda o: o.version)
                    result = {
                        "analysis_type": latest.payload.get("analysis_type"),
                        "samples": latest.payload.get("samples", []),
                        "n_samples": latest.payload.get("n_samples", 0),
                        "n_snp_sites": latest.payload.get("n_snp_sites", 0),
                        "missing_rate": latest.payload.get("missing_rate", 0),
                        "tree_newick": latest.payload.get("tree_newick", ""),
                        "pairwise_distances": latest.payload.get("pairwise_distances", {}),
                        "source": "gom",
                        "object_id": latest.object_id,
                        "version": latest.version,
                    }
                    return json.dumps(result, ensure_ascii=False)
        except Exception:
            logger.exception("GOM SNP lookup failed, falling back to disk")

    snp_json = _RESULTS_DIR / "snp" / "snp_summary.json"
    if not snp_json.exists():
        return json.dumps(
            {
                "error": "SNP tree not available. Run the SNP pipeline first "
                "(snp_calling -> joint_variant_calling -> snp_matrix -> "
                "phylo_tree -> snp_summary), then ingest via "
                "'python scripts/ingest_results.py --snp'."
            }
        )

    try:
        summary = json.loads(snp_json.read_text())
        summary["source"] = "disk"
        return json.dumps(summary, ensure_ascii=False)
    except Exception as e:
        logger.exception("snp_tree failed to read SNP summary")
        return json.dumps({"error": f"Failed to read SNP summary: {e}"})


@tool_handler
def search_samples(args: dict[str, Any], **kwargs: Any) -> str:
    """Search ingested samples by structured genotype fields or full-text query."""
    query = args.get("query", "").strip()
    serotype = args.get("serotype", "").strip()
    mlst_st = args.get("mlst_st", "").strip()
    amr_gene = args.get("amr_gene", "").strip()
    organism = args.get("organism", "").strip()
    limit = args.get("limit", 50)

    db_path = _DEFAULT_DB_PATH
    if not db_path.exists():
        return json.dumps(
            {"error": "GOM database not found. Run 'python scripts/ingest_results.py --all' first."}
        )

    try:
        from hermes_bacmap.services.strain_index import StrainGenotypeIndex

        idx = StrainGenotypeIndex(db_path)
        has_structured = any([serotype, mlst_st, amr_gene, organism])

        if has_structured:
            results = idx.search(
                serotype=serotype or None,
                mlst_st=mlst_st or None,
                amr_gene=amr_gene or None,
                organism=organism or None,
                limit=limit,
            )
            idx.close()

            return json.dumps(
                {
                    "filters": {
                        k: v
                        for k, v in {
                            "serotype": serotype,
                            "mlst_st": mlst_st,
                            "amr_gene": amr_gene,
                            "organism": organism,
                        }.items()
                        if v
                    },
                    "count": len(results),
                    "results": [
                        {
                            "strain_id": m.strain_id,
                            "organism": m.organism,
                            "species": m.species,
                            "serotype": m.serotype or "N/A",
                            "mlst_st": m.mlst_st or "N/A",
                            "amr_genes": sorted(set(m.amr_genes))[:20],
                            "analysis_date": m.analysis_date,
                        }
                        for m in results
                    ],
                },
                ensure_ascii=False,
            )

        idx.close()

        if not query:
            return json.dumps(
                {"error": "Provide at least one of: query, serotype, mlst_st, amr_gene, organism"}
            )

        from hermes_bacmap.services.genome_object_service import GenomeObjectService, ObjectType

        with GenomeObjectService(db_path) as gos:
            fts_results = gos.search(query, object_type=ObjectType.ANALYSIS, limit=limit * 2)

            import re as _re

            st_match = _re.match(r"^ST\s*(\d+)$", query.strip(), _re.IGNORECASE)
            st_number = st_match.group(1) if st_match else None
            query_lower = query.lower()

            matches = []
            seen = set()
            for obj in fts_results:
                if not obj.strain_id:
                    continue
                if obj.strain_id in seen or obj.strain_id.startswith("cohort:"):
                    continue
                seen.add(obj.strain_id)

                p = obj.payload
                sero = p.get("serotype", {})
                serovar = sero.get("sistr", "") if isinstance(sero, dict) else ""

                mlst_raw = p.get("mlst", "")
                st_val = ""
                if mlst_raw and isinstance(mlst_raw, str):
                    parsed_st = parse_mlst(mlst_raw)["st"]
                    if parsed_st != "N/A":
                        st_val = parsed_st

                amr = p.get("amr", {})
                amr_genes = []
                if isinstance(amr, dict):
                    for db_name in ("abricate_card", "abricate_vfdb"):
                        for hit in amr.get(db_name, []):
                            if isinstance(hit, dict) and hit.get("GENE"):
                                amr_genes.append(hit["GENE"])

                reasons = []
                if serovar and query_lower in serovar.lower():
                    reasons.append(f"serotype={serovar}")
                if st_number and st_val == st_number:
                    reasons.append(f"MLST ST={st_val}")
                if any(query_lower in g.lower() for g in amr_genes):
                    matched = [g for g in amr_genes if query_lower in g.lower()][:3]
                    reasons.append(f"AMR: {', '.join(matched)}")
                if not reasons:
                    reasons.append("full-text match")

                matches.append(
                    {
                        "strain_id": obj.strain_id,
                        "organism": obj.organism,
                        "serotype": serovar or "N/A",
                        "mlst_st": f"ST{st_val}" if st_val else "N/A",
                        "amr_genes": sorted(set(amr_genes))[:20],
                        "matched_fields": reasons[:3],
                    }
                )

            return json.dumps(
                {"query": query, "count": len(matches), "results": matches[:limit]},
                ensure_ascii=False,
            )
    except Exception as e:
        logger.exception("search_samples failed")
        return json.dumps({"error": f"Search failed: {e}"})
