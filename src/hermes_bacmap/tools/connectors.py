"""External-database connector handlers — literature and surveillance data.

bio_lit_search queries Europe PMC (PubMed/MEDLINE + preprints) so the agent
can verify putative findings against prior literature; bio_ncbi_pathogen
queries NCBI Pathogen Detection surveillance isolates for comparison with
local outbreak data.
"""

from __future__ import annotations

import json
from typing import Any

from ._common import logger, tool_handler


@tool_handler
def lit_search(args: dict[str, Any], **kwargs: Any) -> str:
    """Search scientific literature (Europe PMC: PubMed + preprints)."""
    query = str(args.get("query", "")).strip()
    max_results = args.get("max_results", 5)

    if not query:
        return json.dumps({"error": "query is required"})

    try:
        from ..services.literature import lit_search as run_search

        result = run_search(query, max_results=int(max_results))
        return json.dumps(result, ensure_ascii=False)
    except (RuntimeError, ValueError) as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("lit_search failed")
        return json.dumps({"error": f"literature search failed for: {query[:100]}"})


@tool_handler
def ncbi_pathogen(args: dict[str, Any], **kwargs: Any) -> str:
    """Query NCBI Pathogen Detection surveillance isolates or AMR elements."""
    action = str(args.get("action", "isolates")).strip()

    try:
        from ..services.ncbi_pathogen import pathogen_amr_elements, pathogen_isolates

        if action == "amr":
            result = pathogen_amr_elements(
                organism=str(args.get("organism", "")),
                element=str(args.get("element", "")),
                geo=str(args.get("geo", "")),
                max_results=int(args.get("max_results", 20)),
            )
        elif action == "isolates":
            result = pathogen_isolates(
                organism=str(args.get("organism", "")),
                geo=str(args.get("geo", "")),
                serovar=str(args.get("serovar", "")),
                year_from=int(args.get("year_from", 0) or 0),
                year_to=int(args.get("year_to", 0) or 0),
                has_ast=bool(args.get("has_ast", False)),
                fq=str(args.get("fq", "")),
                max_results=int(args.get("max_results", 20)),
            )
        else:
            return json.dumps({"error": f"unknown action: {action!r} (isolates|amr)"})
        return json.dumps(result, ensure_ascii=False)
    except (RuntimeError, ValueError) as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("ncbi_pathogen failed")
        return json.dumps({"error": "NCBI pathogen query failed unexpectedly"})
