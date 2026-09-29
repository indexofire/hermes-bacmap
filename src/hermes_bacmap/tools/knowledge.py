"""Knowledge-layer tool handlers — GBrain capture, search, and synthesis.

bio_knowledge_capture records biologically meaningful findings as evidence-
linked knowledge pages (frontmatter: species/gene/strain_group/evidence);
bio_knowledge_search retrieves prior knowledge (hybrid semantic+keyword);
bio_knowledge_think synthesizes an answer with citations and gap analysis.
All degrade gracefully when gbrain is not installed.
"""

from __future__ import annotations

import json
from typing import Any

from ._common import logger, tool_handler


@tool_handler
def knowledge_capture(args: dict[str, Any], **kwargs: Any) -> str:
    """Capture a biologically meaningful finding into the knowledge base."""
    summary = str(args.get("summary", "")).strip()
    if not summary:
        return json.dumps({"error": "summary is required"})

    try:
        from ..services.gbrain_client import capture, capture_evidence

        page = capture_evidence(
            summary=summary,
            species=str(args.get("species", "unknown")),
            gene=str(args.get("gene", "unknown")),
            strain_group=str(args.get("strain_group", "unknown")),
            evidence=str(args.get("evidence", "manual")),
            kind=str(args.get("kind", "finding")),
        )
        receipt = capture(page, what=summary[:120])
        return json.dumps(receipt, ensure_ascii=False)
    except RuntimeError as e:
        return json.dumps({"error": str(e)})
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("knowledge_capture failed")
        return json.dumps({"error": "knowledge_capture failed unexpectedly"})


@tool_handler
def knowledge_search(args: dict[str, Any], **kwargs: Any) -> str:
    """Search the knowledge base (semantic + keyword hybrid)."""
    query = str(args.get("query", "")).strip()
    if not query:
        return json.dumps({"error": "query is required"})

    try:
        from ..services.gbrain_client import search

        results = search(query, limit=int(args.get("limit", 10) or 10))
        top = [
            {
                "slug": r.get("slug", ""),
                "title": r.get("title", ""),
                "snippet": (r.get("chunk_text") or "")[:300],
                "score": r.get("score"),
            }
            for r in results
        ]
        return json.dumps({"query": query, "total": len(top), "results": top}, ensure_ascii=False)
    except RuntimeError as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("knowledge_search failed")
        return json.dumps({"error": "knowledge_search failed unexpectedly"})


@tool_handler
def knowledge_think(args: dict[str, Any], **kwargs: Any) -> str:
    """Synthesize a knowledge-base answer with citations and gap analysis."""
    question = str(args.get("question", "")).strip()
    if not question:
        return json.dumps({"error": "question is required"})

    try:
        from ..services.gbrain_client import think

        result = think(question, anchor=str(args.get("anchor", "") or ""))
        answer = result.get("answer", "")
        citations = [
            {"slug": c.get("slug", ""), "title": c.get("title", "")}
            for c in result.get("citations", [])
            if isinstance(c, dict)
        ]
        return json.dumps(
            {
                "question": question,
                "answer": answer,
                "citations": citations,
                "gaps": result.get("gaps", []),
                "warnings": result.get("warnings", []),
            },
            ensure_ascii=False,
        )
    except RuntimeError as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("knowledge_think failed")
        return json.dumps({"error": "knowledge_think failed unexpectedly"})
