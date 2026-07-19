"""Tool registration table — maps each tool name to its schema and handler.

Consumed by hermes_bacmap.register() to wire all tools into the Hermes
tool registry. Note three tools whose name differs from the handler name:
bio_samtools -> samtools_op, bio_annotate -> annotate_genome,
bio_diagnose -> diagnose_failure.
"""

from collections.abc import Callable
from typing import Any

from hermes_bacmap import schemas
from hermes_bacmap.tools import cli, pipeline, seq, services

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
    ("bio_search_samples", schemas.SEARCH_SAMPLES, services.search_samples),
    ("bio_annotate", schemas.ANNOTATE, pipeline.annotate_genome),
    ("bio_validate_taxonomy", schemas.VALIDATE_TAXONOMY, pipeline.validate_taxonomy),
    ("bio_diagnose", schemas.DIAGNOSE, pipeline.diagnose_failure),
    ("bio_vpa_serotype", schemas.VPA_SEROTYPE, pipeline.vpa_serotype),
    ("bio_query_metadata", schemas.QUERY_METADATA, services.query_metadata),
    ("bio_add_metadata", schemas.ADD_METADATA, services.add_metadata),
    ("bio_query_lab_results", schemas.QUERY_LAB_RESULTS, services.query_lab_results),
    ("bio_add_lab_result", schemas.ADD_LAB_RESULT, services.add_lab_result),
]
