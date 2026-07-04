"""Tool schemas — what the LLM reads to decide when to call each tool."""

# ---------------------------------------------------------------------------
# bio_seq_stats — summarize a FASTA/FASTQ/GenBank file
# ---------------------------------------------------------------------------
SEQ_STATS = {
    "name": "bio_seq_stats",
    "description": (
        "Compute statistics for a sequence file (FASTA, FASTQ, or GenBank). "
        "Returns counts (records, total bases), length distribution "
        "(min/max/mean/N50), and GC content. For FASTQ, also per-base quality "
        "scores and Q-score distribution. Use this as the first step of any "
        "sequencing analysis to understand the input data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file": {
                "type": "string",
                "description": "Absolute or relative path to the sequence file.",
            },
            "format": {
                "type": "string",
                "enum": ["fasta", "fastq", "genbank", "auto"],
                "description": "File format. 'auto' detects from extension (default).",
            },
            "histogram_bins": {
                "type": "integer",
                "description": "Number of bins for length/quality histograms (default 20).",
            },
        },
        "required": ["file"],
    },
}

# ---------------------------------------------------------------------------
# bio_seq_ops — in-memory sequence operations
# ---------------------------------------------------------------------------
SEQ_OPS = {
    "name": "bio_seq_ops",
    "description": (
        "Perform sequence operations: reverse-complement, translate, GC-skew, "
        "motif search, ORF finding, restriction-site detection, k-mer counting. "
        "Operates on a sequence string or a record ID from a loaded file. "
        "Use this for ad-hoc sequence analysis without invoking alignment tools."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "reverse_complement",
                    "translate",
                    "gc_content",
                    "gc_skew",
                    "motif_search",
                    "find_orfs",
                    "restriction_sites",
                    "kmer_count",
                ],
                "description": "Operation to perform.",
            },
            "sequence": {
                "type": "string",
                "description": (
                    "Raw sequence (DNA or RNA). For 'translate' use DNA; codons "
                    "are read from position 0 unless a 'frame' is given."
                ),
            },
            "file": {
                "type": "string",
                "description": "Optional: read sequence(s) from this file instead of 'sequence'.",
            },
            "record_id": {
                "type": "string",
                "description": "If 'file' is given, operate on this specific record.",
            },
            "motif": {
                "type": "string",
                "description": "For 'motif_search': IUPAC motif pattern (e.g. 'GANTC').",
            },
            "frame": {
                "type": "integer",
                "enum": [0, 1, 2],
                "description": "Reading frame for 'translate' (default 0).",
            },
            "min_orf_len": {
                "type": "integer",
                "description": "Minimum ORF length in codons for 'find_orfs' (default 30).",
            },
            "k": {
                "type": "integer",
                "description": "k for 'kmer_count' (default 3).",
            },
            "top": {
                "type": "integer",
                "description": "Return top-N results for 'kmer_count' (default 20).",
            },
            "output_file": {
                "type": "string",
                "description": "Optional: write full result (e.g. all ORFs/k-mers) here.",
            },
        },
        "required": ["operation"],
    },
}

# ---------------------------------------------------------------------------
# bio_fastq_qc — per-read quality control on FASTQ files
# ---------------------------------------------------------------------------
FASTQ_QC = {
    "name": "bio_fastq_qc",
    "description": (
        "Quality control for FASTQ files: per-base quality statistics, adapter "
        "contamination checks, duplication-rate estimate, and length distribution. "
        "Outputs a compact JSON report. For full graphical reports use FastQC via "
        "the shell, but this tool gives quick triage without external tools."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "One or more FASTQ file paths.",
            },
            "sample_reads": {
                "type": "integer",
                "description": "Subsample to at most N reads for speed (0 = all, default 100000).",
            },
            "adapter_file": {
                "type": "string",
                "description": "Optional FASTA of adapter sequences to check for contamination.",
            },
            "report_file": {
                "type": "string",
                "description": "Optional: write a markdown report here in addition to JSON.",
            },
        },
        "required": ["files"],
    },
}

# ---------------------------------------------------------------------------
# bio_seq_convert — convert between sequence file formats
# ---------------------------------------------------------------------------
SEQ_CONVERT = {
    "name": "bio_seq_convert",
    "description": (
        "Convert a sequence file between formats: FASTA, FASTQ, GenBank, EMBL, "
        "NEXUS, PhylIP, Stockholm, Clustal, GFF. Useful before running a tool "
        "that requires a specific input format."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "input_file": {
                "type": "string",
                "description": "Input sequence file.",
            },
            "output_file": {
                "type": "string",
                "description": "Output file path.",
            },
            "output_format": {
                "type": "string",
                "enum": [
                    "fasta", "fastq", "genbank", "embl", "nexus",
                    "phylip", "stockholm", "clustal", "gff",
                ],
                "description": "Target format.",
            },
        },
        "required": ["input_file", "output_file", "output_format"],
    },
}

# ---------------------------------------------------------------------------
# bio_blast — NCBI BLAST search
# ---------------------------------------------------------------------------
BLAST = {
    "name": "bio_blast",
    "description": (
        "Run a BLAST search. Two modes: (1) 'remote' queries the NCBI BLAST API "
        "(requires internet, no local database needed); (2) 'local' runs a local "
        "makeblastdb+blastn/blastp pipeline against a user-provided subject file "
        "(requires the blast+ CLI installed). Use this for sequence identification "
        "and homology discovery."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["remote", "local"],
                "description": "'remote' (NCBI) or 'local' (blast+ CLI).",
            },
            "query": {
                "type": "string",
                "description": (
                    "Query: raw sequence, or path to a FASTA file "
                    "if query_is_file=true."
                ),
            },
            "query_is_file": {
                "type": "boolean",
                "description": "If true, 'query' is a file path.",
            },
            "program": {
                "type": "string",
                "enum": ["blastn", "blastp", "blastx", "tblastn", "tblastx"],
                "description": "BLAST program (default blastn).",
            },
            "database": {
                "type": "string",
                "description": (
                    "Remote: NCBI DB name (nt, nr, refseq_rna, swissprot, etc.). "
                    "Local: subject FASTA file path."
                ),
            },
            "expect": {
                "type": "number",
                "description": "E-value threshold (default 10).",
            },
            "max_hits": {
                "type": "integer",
                "description": "Maximum number of hits to report (default 10).",
            },
            "output_file": {
                "type": "string",
                "description": "Optional: write tabular BLAST output here.",
            },
        },
        "required": ["mode", "query"],
    },
}

# ---------------------------------------------------------------------------
# bio_align — read alignment with BWA / minimap2 / STAR
# ---------------------------------------------------------------------------
ALIGN = {
    "name": "bio_align",
    "description": (
        "Align sequencing reads to a reference genome. Wraps BWA-MEM (short-read DNA), "
        "minimap2 (long-read, RNA-seq), or STAR (RNA-seq splice-aware). Requires the "
        "relevant tool installed. Indexes the reference on first use. Produces a sorted, "
        "indexed BAM by default. Use bio_samtools for downstream SAM/BAM manipulation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "aligner": {
                "type": "string",
                "enum": ["bwa-mem", "minimap2", "star"],
                "description": "Which aligner to use.",
            },
            "reference": {
                "type": "string",
                "description": "Path to reference genome FASTA (will be indexed if needed).",
            },
            "reads": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Read files: 1 for single-end, 2 for paired-end.",
            },
            "output_bam": {
                "type": "string",
                "description": "Output BAM path (sorted + indexed by default).",
            },
            "preset": {
                "type": "string",
                "description": "minimap2 preset: map-pb, map-ont, splice, etc. (minimap2 only).",
            },
            "extra_args": {
                "type": "string",
                "description": "Extra CLI args passed verbatim to the aligner.",
            },
        },
        "required": ["aligner", "reference", "reads", "output_bam"],
    },
}

# ---------------------------------------------------------------------------
# bio_samtools — SAM/BAM manipulation wrapper
# ---------------------------------------------------------------------------
SAMTOOLS = {
    "name": "bio_samtools",
    "description": (
        "Wrap common samtools operations: sort, index, view (filter/region), "
        "depth, flagstat, mpileup, faidx, idxstats. Requires samtools installed. "
        "Use this for any SAM/BAM file manipulation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "sort", "index", "view", "depth", "flagstat",
                    "mpileup", "faidx", "idxstats", "fasta_index",
                ],
                "description": "samtools subcommand to run.",
            },
            "input": {
                "type": "string",
                "description": "Primary input file (BAM/SAM/FASTA).",
            },
            "output": {
                "type": "string",
                "description": "Output file path (where applicable).",
            },
            "region": {
                "type": "string",
                "description": "Genomic region for 'view' (e.g. 'chr1:1000-5000').",
            },
            "flags": {
                "type": "string",
                "description": "samtools view flags (e.g. '-F 4' to exclude unmapped, '-q 30').",
            },
            "extra_args": {
                "type": "string",
                "description": "Extra args passed verbatim to samtools.",
            },
        },
        "required": ["operation", "input"],
    },
}

# ---------------------------------------------------------------------------
# bio_variant — variant calling / manipulation
# ---------------------------------------------------------------------------
VARIANT = {
    "name": "bio_variant",
    "description": (
        "Call or manipulate variants. Operations: 'mpileup_call' (bcftools mpileup+call "
        "from a BAM), 'filter' (bcftools filter on quality/depth), 'query' (bcftools query "
        "to extract fields), 'annotate' (add VCF annotations), 'consensus' (bcftools consensus "
        "to apply variants to a reference). Requires bcftools and/or samtools."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "mpileup_call", "filter", "query", "annotate", "consensus",
                ],
                "description": "Variant operation to perform.",
            },
            "input": {
                "type": "string",
                "description": "Input file (BAM for calling, VCF for filtering/query/annotate).",
            },
            "output": {
                "type": "string",
                "description": "Output file path.",
            },
            "reference": {
                "type": "string",
                "description": "Reference FASTA (required for mpileup_call, consensus, faidx).",
            },
            "query": {
                "type": "string",
                "description": (
                    "bcftools query format string "
                    "(e.g. '%CHROM\\t%POS\\t%REF\\t%ALT\\n')."
                ),
            },
            "filter_expr": {
                "type": "string",
                "description": "bcftools filter expression (e.g. 'QUAL>30 && DP>10').",
            },
            "extra_args": {
                "type": "string",
                "description": "Extra args passed verbatim to bcftools.",
            },
        },
        "required": ["operation", "input"],
    },
}



# ---------------------------------------------------------------------------
# High-level analysis tools (project.md §7 Salmonella pipeline)
# ---------------------------------------------------------------------------

ANALYZE_SALMONELLA = {
    "name": "bio_analyze_salmonella",
    "description": (
        "Run the full pathogen analysis pipeline (QC, assembly, species "
        "identification via invA/uidA/ipaH three-gene routing, MLST, "
        "serotyping, AMR, virulence, plasmid, DEC pathotype, report). "
        "Works for Salmonella, DEC (E. coli), Shigella, EIEC — species "
        "routing is automatic. Returns a summary of results. "
        "For pipeline guidance and troubleshooting, load skill: "
        "skill_view('hermes_bacmap:run-pipeline')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sample_id": {"type": "string", "description": "Sample ID from samples.tsv."},
            "cores": {"type": "integer", "description": "CPU cores (default 8)."},
        },
        "required": ["sample_id"],
    },
}

GET_RESULT = {
    "name": "bio_get_result",
    "description": (
        "Retrieve analysis summary for a completed sample. Returns species "
        "type (Salmonella/E.coli/Shigella), MLST ST, serotype, ipaH status, "
        "DEC pathotype, AMR/virulence/plasmid gene counts. "
        "For result interpretation, load skill: "
        "skill_view('hermes_bacmap:interpret-results')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sample_id": {"type": "string", "description": "Sample ID."},
        },
        "required": ["sample_id"],
    },
}

VERIFY_RESULT = {
    "name": "bio_verify_result",
    "description": (
        "Run deterministic verification on results. Checks species, MLST, "
        "serotype, AMR. Flags critical resistance (CTX-M/NDM/KPC/mcr-1) "
        "for human review. For understanding verification rules, load skill: "
        "skill_view('hermes_bacmap:interpret-results')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sample_id": {"type": "string", "description": "Sample ID."},
        },
        "required": ["sample_id"],
    },
}

GENERATE_REPORT = {
    "name": "bio_generate_report",
    "description": (
        "Generate HTML report with all results, verifier output, and "
        "evidence chain. Returns file path."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sample_id": {"type": "string", "description": "Sample ID."},
        },
        "required": ["sample_id"],
    },
}

LIST_SAMPLES = {
    "name": "bio_list_samples",
    "description": (
        "List all samples and their analysis status."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}


GENE_SCAN = {
    "name": "bio_gene_scan",
    "description": (
        "Scan assembled contigs against a gene database (card/vfdb/ecoh/"
        "plasmidfinder/resfinder) to detect AMR, virulence, serotype, or "
        "plasmid genes. Returns JSON with gene list, identity, coverage. "
        "Supports multi-database scanning in one call. "
        "For AMR gene clinical significance (ESBL/carbapenemase/AmpC), "
        "load skill: skill_view('hermes_bacmap:interpret-results')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "contigs_path": {
                "type": "string",
                "description": "Path to assembled contigs FASTA.",
            },
            "database": {
                "type": "string",
                "description": "Database name: card, vfdb, ecoh, plasmidfinder, resfinder, ncbi, megares, victors, ecoli_vf. Or comma-separated for multi-db.",
            },
            "min_identity": {
                "type": "number",
                "description": "Minimum % identity (default 80).",
            },
            "min_coverage": {
                "type": "number",
                "description": "Minimum % coverage (default 80).",
            },
        },
        "required": ["contigs_path", "database"],
    },
}


SNP_TREE = {
    "name": "bio_snp_tree",
    "description": (
        "Retrieve the cohort-level SNP phylogenetic tree and pairwise "
        "distance matrix. Returns Newick tree string, sample list, "
        "SNP site count, missing rate, and all pairwise SNP distances. "
        "Use this when the user asks about genetic relatedness, "
        "outbreak clusters, phylogenetic relationships, or SNP distances "
        "between samples. For SNP distance interpretation thresholds "
        "(0-5=outbreak, 6-15=possibly related), load skill: "
        "skill_view('hermes_bacmap:interpret-results')."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}


SEARCH_SAMPLES = {
    "name": "bio_search_samples",
    "description": (
        "Search across all ingested sample results in the Genome Object "
        "Model using full-text search. Find samples by organism, serotype, "
        "MLST ST, AMR gene name, plasmid type, or any keyword. Returns "
        "matching samples with their key attributes (species, serotype, "
        "MLST, AMR genes). Use this when the user asks 'which samples "
        "have X' or 'find all Y' type questions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search query. Can be organism name (Salmonella, E.coli), "
                    "serotype (Typhimurium, Enteritidis), MLST ST number "
                    "(ST19, ST11), AMR gene name (blaCTX-M, tetA), or any "
                    "keyword found in sample results."
                ),
            },
        },
        "required": ["query"],
    },
}


ANNOTATE = {
    "name": "bio_annotate",
    "description": (
        "Annotate assembled contigs using a Python-native Prokka replacement. "
        "Predicts CDS with pyrodigal (same algorithm as Prodigal), annotates "
        "via blastp against Prokka protein databases (sprot, IS, AMR), and "
        "outputs structured JSON optimized for AI interpretation. Use this "
        "when the user asks to annotate a genome, find genes, or identify "
        "gene functions in assembled contigs. For gene function interpretation, "
        "load skill: skill_view('hermes_bacmap:interpret-results')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "contigs_path": {
                "type": "string",
                "description": "Path to assembled contigs FASTA file.",
            },
            "sample_id": {
                "type": "string",
                "description": "Sample identifier for locus_tag prefix (optional, auto-detected from path if omitted).",
            },
            "output_path": {
                "type": "string",
                "description": "Output JSON path (optional, default: {sample}/annotation/annotation.json).",
            },
        },
        "required": ["contigs_path"],
    },
}


DIAGNOSE = {
    "name": "bio_diagnose",
    "description": (
        "Diagnose pipeline failures by parsing Snakemake logs. Returns error "
        "type, root cause, affected rule, and suggested recovery commands. "
        "Use this when analysis fails or the user reports pipeline errors. "
        "Handles OOM, lock conflicts, missing tools, missing databases, "
        "missing input files, disk full, and Snakemake version issues."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "log_path": {
                "type": "string",
                "description": "Path to Snakemake log file. If omitted, reads the latest log automatically.",
            },
            "stderr_text": {
                "type": "string",
                "description": "Raw stderr text to diagnose (alternative to log_path).",
            },
        },
    },
}
