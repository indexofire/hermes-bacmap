"""Gene scanner — Python implementation of abricate-like functionality.

Scans assembled contigs against a BLAST database and returns structured JSON
with gene hits, coverage, identity, and database-specific metadata.

Designed as a drop-in replacement for abricate (Perl) with AI-agent friendly
JSON output. Supports any BLAST nucleotide database with abricate-style
headers: >db_name~~~gene~~~accession~~~ product/description

Usage:
    # CLI
    python -m hermes_bacmap.gene_scanner contigs.fasta --db card
    python -m hermes_bacmap.gene_scanner contigs.fasta --db ecoh --json

    # Python API
    from hermes_bacmap.gene_scanner import scan
    result = scan("contigs.fasta", db_name="card")
    genes = result.genes

Database format (FASTA headers, abricate-compatible):
    >db~~~GENE~~~ACCESSION~~~ PRODUCT_OR_DESCRIPTION
    ATGGC...

Custom databases can be added to data/reference/ with:
    gene_scanner.setup_db("mydb", "data/reference/mydb.fasta")
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_MIN_IDENTITY = 80.0
_DEFAULT_MIN_COVERAGE = 80.0
_EVALUE = 1e-10
_WORD_SIZE = 28

_HEADER_RE = re.compile(r">(\S+?)(?:~~~(.+?))?(?:~~~(.+?))?(?:~~~\s*(.+))?")


def normalize_synonyms(raw: dict[str, Any]) -> dict[str, list[str]]:
    """Normalize gene synonym mappings from two input formats.

    Format 1 (canonical → aliases): {"stx1": ["stx1a", "stxA1"]}
    Format 2 (alias → canonical): {"stx1a": "stx1", "stxA1": "stx1"}

    Returns unified Format 1 with lowercase keys.
    """
    if not raw:
        return {}

    result: dict[str, list[str]] = {}
    for key, value in raw.items():
        k = key.strip().lower()
        if isinstance(value, list):
            result[k] = [v.strip().lower() for v in value]
        elif isinstance(value, str):
            canonical = value.strip().lower()
            result.setdefault(canonical, []).append(k)
        else:
            result[k] = []

    return result


def resolve_gene_name(raw_name: str, synonyms: dict[str, list[str]] | None = None) -> str:
    """Resolve a gene name to its canonical form using synonym mapping."""
    if not synonyms:
        return raw_name

    name_lower = raw_name.lower()
    for canonical, aliases in synonyms.items():
        if name_lower == canonical or name_lower in aliases:
            return canonical

    return raw_name


@dataclass
class GeneHit:
    gene: str
    identity: float
    coverage: float
    contig: str
    start: int
    end: int
    strand: str
    accession: str = ""
    product: str = ""
    database: str = ""

    @property
    def hit_length(self) -> int:
        return abs(self.end - self.start) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene": self.gene,
            "identity": self.identity,
            "coverage": self.coverage,
            "contig": self.contig,
            "start": self.start,
            "end": self.end,
            "strand": self.strand,
            "accession": self.accession,
            "product": self.product[:200] if self.product else "",
            "hit_length": self.hit_length,
        }


@dataclass
class ScanResult:
    database: str
    input_file: str
    min_identity: float
    min_coverage: float
    genes: list[GeneHit] = field(default_factory=list)
    total_hits: int = 0
    unique_genes: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "input_file": self.input_file,
            "thresholds": {
                "min_identity": self.min_identity,
                "min_coverage": self.min_coverage,
            },
            "total_hits": self.total_hits,
            "unique_gene_count": len(self.unique_genes),
            "unique_genes": self.unique_genes,
            "genes": [g.to_dict() for g in self.genes],
            "summary": self.summary,
        }

    def build_summary(self) -> dict[str, Any]:
        gene_set = sorted({g.gene for g in self.genes})
        self.unique_genes = gene_set
        self.summary = {
            "total_hits": len(self.genes),
            "unique_genes": len(gene_set),
        }
        return self.summary


_DB_SEARCH_PATHS = [
    Path(__file__).resolve().parents[2] / "data/reference",
    Path(__file__).resolve().parents[2] / ".pixi/envs/default/db",
    Path.home() / ".pixi/envs/default/db",
]


def _find_db(db_name: str) -> Path:
    for base in _DB_SEARCH_PATHS:
        for pattern in [f"{db_name}_blastdb", db_name, f"{db_name}/sequences"]:
            p = base / pattern
            if p.with_suffix(".ndb").exists():
                return p
            if p.is_file() and p.exists():
                return p
    raise FileNotFoundError(
        f"Database '{db_name}' not found. Searched: {[str(p) for p in _DB_SEARCH_PATHS]}. "
        f"Run gene_scanner.setup_db('{db_name}') to create it."
    )


def _parse_db_header(sseqid: str) -> tuple[str, str, str, str]:
    fields = sseqid.split("~~~")
    if len(fields) >= 4:
        return fields[1].strip(), fields[2].strip(), fields[3].strip(), ""
    if len(fields) >= 3:
        return fields[1].strip(), fields[2].strip(), "", ""
    if len(fields) >= 2:
        return fields[1].strip(), "", "", ""
    return sseqid.strip(), "", "", ""


def scan(
    contigs_fasta: str | Path,
    db_name: str = "card",
    *,
    min_identity: float = _DEFAULT_MIN_IDENTITY,
    min_coverage: float = _DEFAULT_MIN_COVERAGE,
    threads: int = 4,
) -> ScanResult:
    """Scan contigs against a gene database.

    Args:
        contigs_fasta: Path to assembled contigs.
        db_name: Database name (card, vfdb, ecoh, plasmidfinder, resfinder, ...).
        min_identity: Minimum % identity.
        min_coverage: Minimum % coverage.
        threads: BLAST threads.

    Returns:
        ScanResult with all gene hits and summary.
    """
    contigs = Path(contigs_fasta)
    if not contigs.exists():
        raise FileNotFoundError(f"Contigs not found: {contigs}")

    db_path = _find_db(db_name)

    from hermes_bacmap.engine import SequenceMatcher

    hits = SequenceMatcher.match(
        query=str(contigs),
        db_prefix=str(db_path),
        mode="blastn",
        min_identity=0.0,
        min_coverage=0.0,
        evalue=_EVALUE,
        word_size=_WORD_SIZE,
        num_threads=threads,
    )

    result = ScanResult(
        database=db_name,
        input_file=str(contigs),
        min_identity=min_identity,
        min_coverage=min_coverage,
    )

    for hit in hits:
        gene, accession, product, _ = _parse_db_header(hit.subject_id)

        if hit.identity < min_identity or hit.subject_coverage < min_coverage:
            continue

        gene_hit = GeneHit(
            gene=gene,
            identity=round(hit.identity, 2),
            coverage=round(hit.subject_coverage, 1),
            contig=hit.query_id,
            start=min(hit.query_start, hit.query_end),
            end=max(hit.query_start, hit.query_end),
            strand=hit.strand,
            accession=accession,
            product=product,
            database=db_name,
        )
        result.genes.append(gene_hit)

    result.genes.sort(key=lambda h: (-h.identity, h.gene))
    result.total_hits = len(result.genes)
    result.build_summary()

    return result


def scan_multi(
    contigs_fasta: str | Path,
    db_names: list[str],
    *,
    min_identity: float = _DEFAULT_MIN_IDENTITY,
    min_coverage: float = _DEFAULT_MIN_COVERAGE,
    threads: int = 4,
) -> dict[str, ScanResult]:
    """Scan contigs against multiple databases.

    Args:
        contigs_fasta: Path to assembled contigs.
        db_names: List of database names.
        min_identity, min_coverage, threads: See scan().

    Returns:
        Dict mapping db_name → ScanResult.
    """
    results = {}
    for db in db_names:
        results[db] = scan(
            contigs_fasta, db_name=db,
            min_identity=min_identity, min_coverage=min_coverage,
            threads=threads,
        )
    return results


def setup_db(db_name: str, fasta_source: Path | str | None = None, output_dir: Path | None = None) -> Path:
    """Build a BLAST database from a FASTA file.

    Args:
        db_name: Name for the database.
        fasta_source: Source FASTA file. If None, tries to find from abricate.
        output_dir: Output directory. Defaults to data/reference/.

    Returns:
        Path to the BLAST DB prefix.
    """
    if output_dir is None:
        output_dir = Path(__file__).resolve().parents[2] / "data/reference"

    output_dir.mkdir(parents=True, exist_ok=True)

    if fasta_source is None:
        for base in _DB_SEARCH_PATHS:
            candidate = base / db_name / "sequences"
            if candidate.exists():
                fasta_source = candidate
                break
        if fasta_source is None:
            raise FileNotFoundError(f"Source FASTA for '{db_name}' not found")

    fasta_source = Path(fasta_source)
    db_prefix = output_dir / f"{db_name}_blastdb"
    local_fasta = output_dir / f"{db_name}_sequences.fasta"

    import shutil
    shutil.copy2(fasta_source, local_fasta)

    subprocess.run([
        "makeblastdb", "-in", str(local_fasta),
        "-dbtype", "nucl", "-out", str(db_prefix),
        "-parse_seqids",
    ], check=True, capture_output=True)

    print(f"✓ BLAST DB '{db_name}' created at {db_prefix}")
    return db_prefix


def setup_all_databases(output_dir: Path | None = None) -> list[str]:
    """Build BLAST databases for all abricate databases found.

    Returns:
        List of created database names.
    """
    abricate_db_dir = Path.home() / ".pixi/envs/default/db"
    if not abricate_db_dir.exists():
        raise FileNotFoundError("abricate db directory not found")

    created = []
    for db_dir in sorted(abricate_db_dir.iterdir()):
        if not db_dir.is_dir():
            continue
        seq_file = db_dir / "sequences"
        if not seq_file.exists():
            continue
        try:
            setup_db(db_dir.name, seq_file, output_dir)
            created.append(db_dir.name)
        except Exception as e:
            print(f"  ✗ {db_dir.name}: {e}")

    return created


def main():
    parser = argparse.ArgumentParser(
        description="Gene scanner — abricate-like gene detection with JSON output"
    )
    parser.add_argument("contigs", help="Assembled contigs FASTA")
    parser.add_argument("--db", default="card", help="Database name (card/vfdb/ecoh/plasmidfinder/...)")
    parser.add_argument("--json", action="store_true", help="Output JSON (default: TSV)")
    parser.add_argument("--multi", help="Comma-separated db names for multi-db scan")
    parser.add_argument("--min-id", type=float, default=_DEFAULT_MIN_IDENTITY)
    parser.add_argument("--min-cov", type=float, default=_DEFAULT_MIN_COVERAGE)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--setup", help="Setup a DB from FASTA: --setup name[,fasta_path]")
    parser.add_argument("--setup-all", action="store_true", help="Setup all abricate databases")
    args = parser.parse_args()

    if args.setup:
        parts = args.setup.split(",")
        db_name = parts[0]
        fasta = parts[1] if len(parts) > 1 else None
        setup_db(db_name, fasta)
        return

    if args.setup_all:
        created = setup_all_databases()
        print(f"Created {len(created)} databases: {', '.join(created)}")
        return

    if args.multi:
        db_names = [d.strip() for d in args.multi.split(",")]
        results = scan_multi(
            args.contigs, db_names,
            min_identity=args.min_id, min_coverage=args.min_cov,
            threads=args.threads,
        )
        if args.json:
            output = {name: r.to_dict() for name, r in results.items()}
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            for name, r in results.items():
                print(f"=== {name}: {r.total_hits} hits, {len(r.unique_genes)} unique genes ===")
                for g in r.genes[:5]:
                    print(f"  {g.gene}\t{g.identity}%\t{g.coverage}%")
        return

    result = scan(
        args.contigs, db_name=args.db,
        min_identity=args.min_id, min_coverage=args.min_cov,
        threads=args.threads,
    )

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"# Database: {result.database}")
        print(f"# Total hits: {result.total_hits}, Unique genes: {len(result.unique_genes)}")
        print("GENE\t%IDENTITY\t%COVERAGE\tCONTIG\tSTART\tEND\tACCESSION")
        for g in result.genes:
            print(f"{g.gene}\t{g.identity}\t{g.coverage}\t{g.contig}\t{g.start}\t{g.end}\t{g.accession}")


if __name__ == "__main__":
    main()
