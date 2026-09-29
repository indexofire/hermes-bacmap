"""Capability-evolution curation handlers — deploy validated discoveries.

bio_db_build turns a validated marker FASTA into a gapit screening
database; bio_marker_register additively writes the marker into
marker_rules.yaml (and optionally the markers FASTA) so subsequent runs of
the species-identification pipeline pick it up automatically.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._common import logger, tool_handler


@tool_handler
def db_build(args: dict[str, Any], **kwargs: Any) -> str:
    """Build a custom gapit screening database from a marker FASTA."""
    name = str(args.get("name", "")).strip()
    fasta = str(args.get("fasta", "")).strip()

    if not name or not fasta:
        return json.dumps({"error": "name and fasta are required"})

    try:
        from ..services.gapit_ops import db_build as run_build

        result = run_build(
            name,
            Path(fasta),
            description=str(args.get("description", "")),
            dbtype=str(args.get("dbtype", "")),
            force=bool(args.get("force", False)),
        )
        return json.dumps(result, ensure_ascii=False)
    except (RuntimeError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("db_build failed")
        return json.dumps({"error": f"db_build failed for {name!r}"})


@tool_handler
def marker_register(args: dict[str, Any], **kwargs: Any) -> str:
    """Register a validated marker into marker_rules.yaml (additive, backed up)."""
    species = str(args.get("species", "")).strip()
    gene = str(args.get("gene", "")).strip()

    if not species or not gene:
        return json.dumps({"error": "species and gene are required"})

    try:
        from ..services.marker_registry import register_marker

        result = register_marker(
            species,
            gene,
            sequence_fasta=Path(args["sequence_fasta"]) if args.get("sequence_fasta") else None,
            min_identity=int(args.get("min_identity", 90) or 90),
            min_hits=int(args.get("min_hits", 1) or 1),
        )
        result["knowledge"] = _capture_registration_knowledge(result)
        return json.dumps(result, ensure_ascii=False)
    except (ValueError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("marker_register failed")
        return json.dumps({"error": f"marker_register failed for {gene!r}"})


def _capture_registration_knowledge(result: dict[str, Any]) -> dict[str, Any] | None:
    import os

    if result.get("action") == "already_present":
        return None
    if os.environ.get("BACMAP_KNOWLEDGE_HOOKS") == "0":
        return None
    try:
        from ..services.gbrain_client import capture

        page = (
            f"Marker registered: {result['gene']} for {result['species']} "
            f"(min_identity {result['min_identity']}, genes now: {', '.join(result['genes'])})."
        )
        receipt = capture(page, what=f"register {result['gene']}")
        return {"state": receipt.get("state", ""), "slug": receipt.get("slug", "")}
    except Exception:
        return None
