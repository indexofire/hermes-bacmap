"""Tool registration table — maps each tool name to its schema and handler.

Consumed by hermes_bacmap.register() to wire all tools into the Hermes
tool registry. Note three tools whose name differs from the handler name:
bio_samtools -> samtools_op, bio_annotate -> annotate_genome,
bio_diagnose -> diagnose_failure.
"""

from collections.abc import Callable
from typing import Any

from .. import schemas
from . import curation, cli, connectors, discovery, pipeline, sandbox, seq, services

Handler = Callable[..., str]

_TOOL_REGISTRY: list[tuple[str, dict[str, Any], Handler]] = [
    ("bio_seq_stats", schemas.SEQ_STATS, seq.seq_stats),
    ("bio_seq_ops", schemas.SEQ_OPS, seq.seq_ops),
    ("bio_fastq_qc", schemas.FASTQ_QC, seq.fastq_qc),
    ("bio_seq_convert", schemas.SEQ_CONVERT, seq.seq_convert),
    ("bio_blast", schemas.BLAST, cli.blast),
    ("bio_align", schemas.ALIGN, cli.align),
    ("bio_samtools", schemas.SAMTOOLS, cli.samtools_op),
    ("bio_variant", schemas.VARIANT, cli.variant),
    # High-level analysis tools (project.md §7)
    ("bio_analyze_pathogen", schemas.ANALYZE_PATHOGEN, pipeline.analyze_pathogen),
    ("bio_get_result", schemas.GET_RESULT, pipeline.get_result),
    ("bio_verify_result", schemas.VERIFY_RESULT, pipeline.verify_result),
    ("bio_generate_report", schemas.GENERATE_REPORT, pipeline.generate_report),
    ("bio_list_samples", schemas.LIST_SAMPLES, pipeline.list_samples),
    ("bio_gene_scan", schemas.GENE_SCAN, pipeline.gene_scan),
    ("bio_snp_tree", schemas.SNP_TREE, services.snp_tree),
    ("bio_cgmlst", schemas.CGLST_TRACEBACK, services.cgmlst_traceback),
    ("bio_search_samples", schemas.SEARCH_SAMPLES, services.search_samples),
    ("bio_review_flags", schemas.REVIEW_FLAGS, services.review_flags),
    ("bio_annotate", schemas.ANNOTATE, pipeline.annotate_genome),
    ("bio_validate_taxonomy", schemas.VALIDATE_TAXONOMY, pipeline.validate_taxonomy),
    ("bio_diagnose", schemas.DIAGNOSE, pipeline.diagnose_failure),
    ("bio_vpa_serotype", schemas.VPA_SEROTYPE, pipeline.vpa_serotype),
    ("bio_query_metadata", schemas.QUERY_METADATA, services.query_metadata),
    ("bio_add_metadata", schemas.ADD_METADATA, services.add_metadata),
    ("bio_query_lab_results", schemas.QUERY_LAB_RESULTS, services.query_lab_results),
    ("bio_add_lab_result", schemas.ADD_LAB_RESULT, services.add_lab_result),
    ("bio_species_compare", schemas.SPECIES_COMPARE, services.species_compare),
    ("bio_db_setup", schemas.DB_SETUP, services.db_setup),
    ("bio_db_status", schemas.DB_STATUS, services.db_status),
    ("bio_pangenome", schemas.PANGENOME, discovery.pangenome),
    ("bio_analytics_query", schemas.ANALYTICS_QUERY, discovery.analytics_query),
    ("bio_differential_genes", schemas.DIFFERENTIAL_GENES, discovery.differential_genes),
    ("bio_lit_search", schemas.LIT_SEARCH, connectors.lit_search),
    ("bio_ncbi_pathogen", schemas.NCBI_PATHOGEN, connectors.ncbi_pathogen),
    ("bio_sandbox_exec", schemas.SANDBOX_EXEC, sandbox.sandbox_exec),
    ("bio_sql_query", schemas.SQL_QUERY, sandbox.sql_query),
    ("bio_plot", schemas.PLOT, sandbox.plot),
    ("bio_db_build", schemas.DB_BUILD, curation.db_build),
    ("bio_marker_register", schemas.MARKER_REGISTER, curation.marker_register),
]
