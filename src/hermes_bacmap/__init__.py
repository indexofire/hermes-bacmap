"""hermes_bacmap plugin — registration."""

import logging

from . import schemas, tools

logger = logging.getLogger(__name__)


def register(ctx):
    """Wire schemas to handlers and register with the Hermes tool registry."""
    ctx.register_tool(
        name="bio_seq_stats",
        toolset="bioinfo",
        schema=schemas.SEQ_STATS,
        handler=tools.seq_stats,
    )
    ctx.register_tool(
        name="bio_seq_ops",
        toolset="bioinfo",
        schema=schemas.SEQ_OPS,
        handler=tools.seq_ops,
    )
    ctx.register_tool(
        name="bio_fastq_qc",
        toolset="bioinfo",
        schema=schemas.FASTQ_QC,
        handler=tools.fastq_qc,
    )
    ctx.register_tool(
        name="bio_seq_convert",
        toolset="bioinfo",
        schema=schemas.SEQ_CONVERT,
        handler=tools.seq_convert,
    )
    ctx.register_tool(
        name="bio_blast",
        toolset="bioinfo",
        schema=schemas.BLAST,
        handler=tools.blast,
    )
    ctx.register_tool(
        name="bio_align",
        toolset="bioinfo",
        schema=schemas.ALIGN,
        handler=tools.align,
    )
    ctx.register_tool(
        name="bio_samtools",
        toolset="bioinfo",
        schema=schemas.SAMTOOLS,
        handler=tools.samtools_op,
    )
    ctx.register_tool(
        name="bio_variant",
        toolset="bioinfo",
        schema=schemas.VARIANT,
        handler=tools.variant,
    )

    # High-level analysis tools (project.md §7)
    ctx.register_tool(
        name="bio_analyze_salmonella",
        toolset="bioinfo",
        schema=schemas.ANALYZE_SALMONELLA,
        handler=tools.analyze_salmonella,
    )
    ctx.register_tool(
        name="bio_get_result",
        toolset="bioinfo",
        schema=schemas.GET_RESULT,
        handler=tools.get_result,
    )
    ctx.register_tool(
        name="bio_verify_result",
        toolset="bioinfo",
        schema=schemas.VERIFY_RESULT,
        handler=tools.verify_result,
    )
    ctx.register_tool(
        name="bio_generate_report",
        toolset="bioinfo",
        schema=schemas.GENERATE_REPORT,
        handler=tools.generate_report,
    )
    ctx.register_tool(
        name="bio_list_samples",
        toolset="bioinfo",
        schema=schemas.LIST_SAMPLES,
        handler=tools.list_samples,
    )
    ctx.register_tool(
        name="bio_gene_scan",
        toolset="bioinfo",
        schema=schemas.GENE_SCAN,
        handler=tools.gene_scan,
    )
    ctx.register_tool(
        name="bio_snp_tree",
        toolset="bioinfo",
        schema=schemas.SNP_TREE,
        handler=tools.snp_tree,
    )
    ctx.register_tool(
        name="bio_search_samples",
        toolset="bioinfo",
        schema=schemas.SEARCH_SAMPLES,
        handler=tools.search_samples,
    )
    ctx.register_tool(
        name="bio_annotate",
        toolset="bioinfo",
        schema=schemas.ANNOTATE,
        handler=tools.annotate_genome,
    )
    ctx.register_tool(
        name="bio_validate_taxonomy",
        toolset="bioinfo",
        schema=schemas.VALIDATE_TAXONOMY,
        handler=tools.validate_taxonomy,
    )
    ctx.register_tool(
        name="bio_diagnose",
        toolset="bioinfo",
        schema=schemas.DIAGNOSE,
        handler=tools.diagnose_failure,
    )
    ctx.register_tool(
        name="bio_vpa_serotype",
        toolset="bioinfo",
        schema=schemas.VPA_SEROTYPE,
        handler=tools.vpa_serotype,
    )
    ctx.register_tool(
        name="bio_query_metadata",
        toolset="bioinfo",
        schema=schemas.QUERY_METADATA,
        handler=tools.query_metadata,
    )
    ctx.register_tool(
        name="bio_add_metadata",
        toolset="bioinfo",
        schema=schemas.ADD_METADATA,
        handler=tools.add_metadata,
    )
    ctx.register_tool(
        name="bio_query_lab_results",
        toolset="bioinfo",
        schema=schemas.QUERY_LAB_RESULTS,
        handler=tools.query_lab_results,
    )
    ctx.register_tool(
        name="bio_add_lab_result",
        toolset="bioinfo",
        schema=schemas.ADD_LAB_RESULT,
        handler=tools.add_lab_result,
    )

    # Bundle skills with common pipeline guidance.
    # Skills live at <project_root>/skills/ — two levels up from this file
    # (src/hermes_bacmap/__init__.py → ../../skills/).
    from pathlib import Path

    skills_dir = Path(__file__).resolve().parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)

    logger.info("hermes_bacmap plugin registered 24 tools")
