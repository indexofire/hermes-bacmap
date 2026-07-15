"""Tool handlers — the code that runs when the LLM calls each tool.

Design principles:
  - Python-only tools (seq_stats, seq_ops, fastq_qc, seq_convert) use Biopython
    and degrade gracefully if Biopython is not installed (lazy install).
  - External-CLI tools (blast, align, samtools, variant) detect the binary at
    call time and return a clear error JSON if missing — never raise.
  - All handlers return JSON strings. Errors are {"error": "..."}.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from hermes_bacmap.config import PROJECT_ROOT as _PROJECT_ROOT, RESULTS_DIR as _RESULTS_DIR, DB_PATH as _DEFAULT_DB_PATH  # noqa: E402
from hermes_bacmap.config import PIXI_BIN, PIXI_PYTHON  # noqa: E402

logger = logging.getLogger(__name__)

_BIOPYTHON_AVAILABLE: bool | None = None


_PIXI_ENV: dict[str, str] = dict(os.environ)
_PIXI_ENV["PATH"] = ":".join([PIXI_BIN, _PIXI_ENV.get("PATH", "")])


def _run_project_script(script_name: str, args: list[str], timeout: int = 3600) -> str:
    """Run a script from scripts/ with pixi PATH injected. Returns stdout or error JSON."""
    env = dict(_PIXI_ENV)
    cmd = [PIXI_PYTHON, str(_PROJECT_ROOT / "scripts" / script_name)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    if result.returncode != 0:
        return json.dumps({"error": f"{script_name} failed", "stderr": result.stderr[-500:]})
    return result.stdout


def _ensure_biopython() -> bool:
    """Return True if Biopython can be imported; try lazy install once."""
    global _BIOPYTHON_AVAILABLE
    if _BIOPYTHON_AVAILABLE is not None:
        return _BIOPYTHON_AVAILABLE
    try:
        import Bio  # noqa: F401

        _BIOPYTHON_AVAILABLE = True
        return True
    except ImportError:
        pass
    try:
        subprocess.run(
            [PIXI_PYTHON, "-m", "pip", "install", "biopython"],
            check=True,
            capture_output=True,
            timeout=120,
        )
        import Bio  # noqa: F401

        _BIOPYTHON_AVAILABLE = True
        return True
    except Exception as e:
        logger.warning("Biopython not available and lazy install failed: %s", e)
    _BIOPYTHON_AVAILABLE = False
    return False


def _which_or_error(cmd: str) -> str | None:
    """Return path to cmd or None. Caller shows a helpful error."""
    return shutil.which(cmd)


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------


def _resolve_path(p: str) -> str:
    """Expand ~ and make absolute."""
    return os.path.abspath(os.path.expanduser(p))


def _detect_format(path: str, hint: str = "auto") -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    aliases = {
        "fa": "fasta",
        "fna": "fasta",
        "ffn": "fasta",
        "faa": "fasta",
        "frn": "fasta",
        "fq": "fastq",
        "gb": "genbank",
        "gbk": "genbank",
    }
    fmt = aliases.get(ext, ext)
    if hint != "auto":
        return hint
    return fmt if fmt else "fasta"


def _run_cmd(cmd: list[str], timeout: int = 3600) -> dict[str, Any]:
    """Run a subprocess, return {returncode, stdout, stderr}."""
    logger.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_PIXI_ENV,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-8000:] if len(proc.stdout) > 8000 else proc.stdout,
        "stderr": proc.stderr[-4000:] if len(proc.stderr) > 4000 else proc.stderr,
    }


# ---------------------------------------------------------------------------
# bio_seq_stats
# ---------------------------------------------------------------------------


def seq_stats(args: dict, **kwargs) -> str:
    path = _resolve_path(args.get("file", ""))
    if not os.path.isfile(path):
        return json.dumps({"error": f"File not found: {path}"})
    fmt = args.get("format", "auto")
    fmt = _detect_format(path, fmt)
    bins = args.get("histogram_bins", 20)

    if not _ensure_biopython():
        return json.dumps({"error": "Biopython is required. Run: pip install biopython"})

    try:
        from Bio import SeqIO  # type: ignore

        records = list(SeqIO.parse(path, fmt))
    except Exception as e:
        return json.dumps({"error": f"Failed to parse {fmt} file: {e}"})

    if not records:
        return json.dumps({"error": f"No records found in {fmt} file"})

    lengths = [len(r) for r in records]
    gc_total = 0
    total_bases = sum(lengths)
    for r in records:
        s = str(r.seq).upper()
        gc_total += s.count("G") + s.count("C")

    n50 = _calc_n50(lengths)

    result = {
        "file": path,
        "format": fmt,
        "record_count": len(records),
        "total_bases": total_bases,
        "length": {
            "min": min(lengths),
            "max": max(lengths),
            "mean": round(total_bases / len(lengths), 2),
            "median": _median(lengths),
            "n50": n50,
        },
        "gc_content": round(gc_total / total_bases * 100, 3) if total_bases else 0,
        "length_histogram": _histogram(lengths, bins),
    }

    # FASTQ-specific: quality
    if fmt == "fastq":
        try:
            phred_scores = []
            quals_per_pos: list[list[float]] = []
            for r in records[:5000]:  # sample for speed
                if r.letter_annotations.get("phred_quality"):
                    q = r.letter_annotations["phred_quality"]
                    phred_scores.extend(q)
                    for i, v in enumerate(q):
                        while len(quals_per_pos) <= i:
                            quals_per_pos.append([])
                        quals_per_pos[i].append(v)
            if phred_scores:
                result["quality"] = {
                    "mean_q": round(sum(phred_scores) / len(phred_scores), 2),
                    "q20_fraction": round(
                        sum(1 for q in phred_scores if q >= 20) / len(phred_scores), 4
                    ),
                    "q30_fraction": round(
                        sum(1 for q in phred_scores if q >= 30) / len(phred_scores), 4
                    ),
                    "per_position_mean_q": [round(sum(p) / len(p), 2) for p in quals_per_pos[:200]],
                }
        except Exception as e:
            result["quality_error"] = str(e)

    # Top 10 longest records
    by_len = sorted([(r.id, len(r)) for r in records], key=lambda x: -x[1])[:10]
    result["top_records_by_length"] = [{"id": rid, "length": rl} for rid, rl in by_len]

    return json.dumps(result, indent=2)


def _calc_n50(lengths: list[int]) -> int:
    sorted_lens = sorted(lengths, reverse=True)
    cumsum = 0
    half = sum(sorted_lens) / 2
    for length in sorted_lens:
        cumsum += length
        if cumsum >= half:
            return length
    return 0


def _median(values: list) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0
    if n % 2 == 0:
        return round((s[n // 2 - 1] + s[n // 2]) / 2, 2)
    return s[n // 2]


def _histogram(values: list, bins: int = 20) -> list[dict]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [{"bin": f"{lo}", "count": len(values)}]
    width = (hi - lo) / bins
    buckets = [0] * bins
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        buckets[idx] += 1
    return [
        {"bin": f"{round(lo + i * width)}-{round(lo + (i + 1) * width)}", "count": b}
        for i, b in enumerate(buckets)
    ]


# ---------------------------------------------------------------------------
# bio_seq_ops
# ---------------------------------------------------------------------------

_COMPLEMENT = str.maketrans("ACGTUNacgtun", "TGCAANtgcaan")
_IUPAC = {
    "A": "A",
    "C": "C",
    "G": "G",
    "T": "T",
    "U": "U",
    "R": "[AG]",
    "Y": "[CT]",
    "S": "[GC]",
    "W": "[AT]",
    "K": "[GT]",
    "M": "[AC]",
    "B": "[CGT]",
    "D": "[AGT]",
    "H": "[ACT]",
    "V": "[ACG]",
    "N": "[ACGTN]",
}


def _get_sequence(args: dict) -> tuple[str | None, str]:
    """Get sequence from args, return (sequence, error_or_empty)."""
    seq = args.get("sequence")
    if seq:
        return seq.upper(), ""
    filepath = args.get("file")
    if not filepath:
        return None, "Provide 'sequence' or 'file'."
    path = _resolve_path(filepath)
    if not os.path.isfile(path):
        return None, f"File not found: {path}"
    if not _ensure_biopython():
        return None, "Biopython required for file input."
    from Bio import SeqIO  # type: ignore

    rid = args.get("record_id")
    for rec in SeqIO.parse(path, _detect_format(path)):
        if rid is None or rec.id == rid:
            return str(rec.seq).upper(), ""
    return None, f"Record '{rid}' not found in {path}."


def seq_ops(args: dict, **kwargs) -> str:
    op = args.get("operation", "")
    if not op:
        return json.dumps({"error": "Specify 'operation'."})

    if op == "reverse_complement":
        seq, err = _get_sequence(args)
        if err:
            return json.dumps({"error": err})
        rc = seq.translate(_COMPLEMENT)[::-1]
        return json.dumps({"input_length": len(seq), "reverse_complement": rc})

    if op == "translate":
        seq, err = _get_sequence(args)
        if err:
            return json.dumps({"error": err})
        if not _ensure_biopython():
            return json.dumps({"error": "Biopython required for translation."})
        from Bio.Seq import Seq  # type: ignore

        frame = args.get("frame", 0)
        protein = str(Seq(seq[frame:]).translate())
        return json.dumps(
            {
                "input_length": len(seq),
                "frame": frame,
                "protein": protein,
                "protein_length": len(protein),
            }
        )

    if op == "gc_content":
        seq, err = _get_sequence(args)
        if err:
            return json.dumps({"error": err})
        gc = seq.count("G") + seq.count("C")
        return json.dumps(
            {
                "length": len(seq),
                "gc_count": gc,
                "gc_content": round(gc / len(seq) * 100, 3) if seq else 0,
            }
        )

    if op == "gc_skew":
        seq, err = _get_sequence(args)
        if err:
            return json.dumps({"error": err})
        window = args.get("window", 1000)
        skew_vals = []
        for i in range(0, len(seq), window):
            chunk = seq[i : i + window]
            g = chunk.count("G")
            c = chunk.count("C")
            skew = (g - c) / (g + c) if (g + c) else 0
            skew_vals.append({"pos": i, "skew": round(skew, 4)})
        return json.dumps({"window_size": window, "skew_profile": skew_vals})

    if op == "motif_search":
        seq, err = _get_sequence(args)
        if err:
            return json.dumps({"error": err})
        motif = args.get("motif", "").upper()
        if not motif:
            return json.dumps({"error": "Provide 'motif' (IUPAC pattern)."})
        regex = "".join(_IUPAC.get(c, c) for c in motif)
        matches = [(m.start(), m.end()) for m in re.finditer(regex, seq)]
        return json.dumps(
            {
                "motif": motif,
                "match_count": len(matches),
                "positions": matches[:200],
            }
        )

    if op == "find_orfs":
        seq, err = _get_sequence(args)
        if err:
            return json.dumps({"error": err})
        min_len = args.get("min_orf_len", 30)
        orfs = _find_orfs(seq, min_len)
        return json.dumps(
            {
                "min_orf_length": min_len,
                "orf_count": len(orfs),
                "orfs": orfs[:100],
            }
        )

    if op == "restriction_sites":
        seq, err = _get_sequence(args)
        if err:
            return json.dumps({"error": err})
        # Common restriction enzymes
        enzymes = {
            "EcoRI": "GAATTC",
            "BamHI": "GGATCC",
            "HindIII": "AAGCTT",
            "XhoI": "CTCGAG",
            "NotI": "GCGGCCGC",
            "NheI": "GCTAGC",
            "SacI": "GAGCTC",
            "KpnI": "GGTACC",
            "PstI": "CTGCAG",
            "SmaI": "CCCGGG",
            "SalI": "GTCGAC",
        }
        sites = {}
        for name, site in enzymes.items():
            pos = [m.start() for m in re.finditer(site, seq)]
            if pos:
                sites[name] = {"sequence": site, "positions": pos[:50], "count": len(pos)}
        return json.dumps({"restriction_sites": sites})

    if op == "kmer_count":
        seq, err = _get_sequence(args)
        if err:
            return json.dumps({"error": err})
        k = args.get("k", 3)
        top = args.get("top", 20)
        kmers = Counter(seq[i : i + k] for i in range(len(seq) - k + 1))
        top_kmers = [
            {"kmer": km, "count": cnt, "frequency": round(cnt / len(seq), 5)}
            for km, cnt in kmers.most_common(top)
        ]
        out_file = args.get("output_file")
        if out_file:
            with open(out_file, "w") as f:
                for km, cnt in kmers.most_common():
                    f.write(f"{km}\t{cnt}\n")
        return json.dumps({"k": k, "unique_kmers": len(kmers), "top": top_kmers})

    return json.dumps({"error": f"Unknown operation: {op}"})


def _find_orfs(seq: str, min_codons: int = 30) -> list[dict]:
    """Find ORFs in all 6 frames."""
    comp = seq.translate(_COMPLEMENT)[::-1]
    targets = [(seq, "+", f) for f in range(3)] + [(comp, "-", f) for f in range(3)]
    orfs = []
    codon_re = re.compile(r"(ATG(?:\w{3})*?(?:TAA|TAG|TGA))")
    for target, strand, frame in targets:
        sub = target[frame:]
        for m in codon_re.finditer(sub):
            orf_seq = m.group(1)
            if len(orf_seq) // 3 >= min_codons:
                orfs.append(
                    {
                        "start": m.start() + frame,
                        "end": m.end() + frame,
                        "strand": strand,
                        "frame": frame,
                        "length_codons": len(orf_seq) // 3,
                        "protein": orf_seq[:120] + ("..." if len(orf_seq) > 120 else ""),
                    }
                )
    orfs.sort(key=lambda x: -x["length_codons"])
    return orfs


# ---------------------------------------------------------------------------
# bio_fastq_qc
# ---------------------------------------------------------------------------


def fastq_qc(args: dict, **kwargs) -> str:
    files = args.get("files", [])
    if not files:
        return json.dumps({"error": "Provide at least one FASTQ 'files' path."})
    if not _ensure_biopython():
        return json.dumps({"error": "Biopython required. Run: pip install biopython"})

    sample_reads = args.get("sample_reads", 100000)
    report: dict[str, Any] = {"files": [], "summary": {}}
    all_lens: list[int] = []
    all_q: list[float] = []

    for fp in files:
        path = _resolve_path(fp)
        if not os.path.isfile(path):
            report["files"].append({"file": fp, "error": "not found"})
            continue
        try:
            from Bio import SeqIO  # type: ignore

            lengths = []
            quals_per_pos: dict[int, list[float]] = {}
            ids = []
            n = 0
            for rec in SeqIO.parse(path, "fastq"):
                if sample_reads and n >= sample_reads:
                    break
                lengths.append(len(rec))
                ids.append(rec.id)
                for i, q in enumerate(rec.letter_annotations.get("phred_quality", [])):
                    quals_per_pos.setdefault(i, []).append(q)
                n += 1

            file_report = {
                "file": fp,
                "reads_sampled": n,
                "length_min": min(lengths) if lengths else 0,
                "length_max": max(lengths) if lengths else 0,
                "length_mean": round(sum(lengths) / len(lengths), 2) if lengths else 0,
                "per_position_mean_q": [
                    round(sum(v) / len(v), 2) for _, v in sorted(quals_per_pos.items())[:200]
                ],
            }
            all_lens.extend(lengths)
            all_q.extend(q for v in quals_per_pos.values() for q in v)

            # Duplication estimate
            if ids:
                unique = len(set(ids))
                file_report["duplication_rate"] = round(1 - unique / len(ids), 4)

            report["files"].append(file_report)
        except Exception as e:
            report["files"].append({"file": fp, "error": str(e)})

    # Adapter check
    adapter_file = args.get("adapter_file")
    if adapter_file and os.path.isfile(adapter_file) and all_lens:
        try:
            report["adapter_contamination"] = _check_adapters(files[0], adapter_file)
        except Exception as e:
            report["adapter_error"] = str(e)

    if all_q:
        report["summary"]["overall_mean_q"] = round(sum(all_q) / len(all_q), 2)
        report["summary"]["q30_fraction"] = round(sum(1 for q in all_q if q >= 30) / len(all_q), 4)
        report["summary"]["q20_fraction"] = round(sum(1 for q in all_q if q >= 20) / len(all_q), 4)
    if all_lens:
        report["summary"]["total_reads_sampled"] = len(all_lens)
        report["summary"]["length_distribution"] = _histogram(all_lens, 20)

    md_path = args.get("report_file")
    if md_path:
        _write_fastq_md(md_path, report)

    return json.dumps(report, indent=2)


def _check_adapters(fastq_path: str, adapter_fasta: str) -> dict:
    from Bio import SeqIO  # type: ignore

    adapters = [str(r.seq) for r in SeqIO.parse(adapter_fasta, "fasta")]
    counts = {a[:20]: 0 for a in adapters}
    total = 0
    for rec in SeqIO.parse(fastq_path, "fastq"):
        if total >= 50000:
            break
        seq = str(rec.seq)
        for a in adapters:
            if a[:20] in seq:
                counts[a[:20]] += 1
        total += 1
    return {
        "total_checked": total,
        "adapters": counts,
        "contamination_rate": {k: round(v / total, 4) for k, v in counts.items()} if total else {},
    }


def _write_fastq_md(path: str, report: dict):
    with open(path, "w") as f:
        f.write("# FASTQ Quality Control Report\n\n")
        s = report.get("summary", {})
        f.write(f"**Reads sampled:** {s.get('total_reads_sampled', 'N/A')}\n\n")
        if "overall_mean_q" in s:
            f.write(f"**Mean quality:** Q{s['overall_mean_q']}\n\n")
            f.write(f"**Q30 fraction:** {s.get('q30_fraction', 'N/A')}\n\n")
        for fr in report.get("files", []):
            f.write(f"## {fr.get('file', '?')}\n\n")
            if "error" in fr:
                f.write(f"Error: {fr['error']}\n\n")
                continue
            f.write(f"- Reads sampled: {fr.get('reads_sampled')}\n")
            f.write(
                f"- Length: {fr.get('length_min')}-{fr.get('length_max')} "
                f"(mean {fr.get('length_mean')})\n"
            )
            if "duplication_rate" in fr:
                f.write(f"- Duplication rate: {fr['duplication_rate']:.1%}\n")
            f.write("\n")


# ---------------------------------------------------------------------------
# bio_seq_convert
# ---------------------------------------------------------------------------

# Mapping our format names to Biopython SeqIO format keys
_BIO_FORMAT_MAP = {
    "fasta": "fasta",
    "fastq": "fastq",
    "genbank": "genbank",
    "embl": "embl",
    "nexus": "nexus",
    "phylip": "phylip",
    "stockholm": "stockholm",
    "clustal": "clustal",
}


def seq_convert(args: dict, **kwargs) -> str:
    inp = _resolve_path(args.get("input_file", ""))
    outp = _resolve_path(args.get("output_file", ""))
    out_fmt = args.get("output_format", "fasta")

    if not os.path.isfile(inp):
        return json.dumps({"error": f"Input not found: {inp}"})
    if not outp:
        return json.dumps({"error": "Provide 'output_file'."})
    if not _ensure_biopython():
        return json.dumps({"error": "Biopython required. Run: pip install biopython"})

    in_fmt = _detect_format(inp)
    bio_out = _BIO_FORMAT_MAP.get(out_fmt, out_fmt)

    try:
        from Bio import SeqIO  # type: ignore

        records = list(SeqIO.parse(inp, in_fmt))
        if not records:
            return json.dumps({"error": f"No records in {inp} ({in_fmt})"})
        # GenBank/EMBL require molecule_type annotation — add a default if missing
        if bio_out in ("genbank", "embl"):
            for rec in records:
                if "molecule_type" not in rec.annotations:
                    rec.annotations["molecule_type"] = "DNA"
        count = SeqIO.write(records, outp, bio_out)
        return json.dumps(
            {
                "input_file": inp,
                "input_format": in_fmt,
                "output_file": outp,
                "output_format": bio_out,
                "records_converted": count,
            }
        )
    except Exception as e:
        return json.dumps({"error": f"Conversion failed: {e}"})


# ---------------------------------------------------------------------------
# bio_blast
# ---------------------------------------------------------------------------


def blast(args: dict, **kwargs) -> str:
    mode = args.get("mode", "remote")
    query = args.get("query", "")
    if not query:
        return json.dumps({"error": "Provide 'query'."})

    program = args.get("program", "blastn")
    evalue = args.get("expect", 10)
    max_hits = args.get("max_hits", 10)
    out_file = args.get("output_file")

    if mode == "remote":
        return _blast_remote(
            query,
            args.get("query_is_file", False),
            program,
            args.get("database", "nt"),
            evalue,
            max_hits,
            out_file,
        )
    elif mode == "local":
        return _blast_local(
            query,
            args.get("query_is_file", False),
            program,
            args.get("database", ""),
            evalue,
            max_hits,
            out_file,
        )
    return json.dumps({"error": f"Unknown mode: {mode}"})


def _blast_remote(
    query: str,
    is_file: bool,
    program: str,
    db: str,
    evalue: float,
    max_hits: int,
    out_file: str | None,
) -> str:
    if not _ensure_biopython():
        return json.dumps({"error": "Biopython required. Run: pip install biopython"})
    try:
        from Bio.Blast import NCBIWWW, NCBIXML  # type: ignore
    except Exception as e:
        return json.dumps({"error": f"Blast module import failed: {e}"})

    query_str = query
    if is_file:
        with open(query) as f:
            query_str = f.read()

    try:
        result_handle = NCBIWWW.qblast(
            program,
            db,
            query_str,
            expect=evalue,
            hitlist_size=max_hits,
        )
        blast_records = list(NCBIXML.parse(result_handle))
    except Exception as e:
        return json.dumps({"error": f"NCBI BLAST failed: {e}"})

    hits = []
    for rec in blast_records:
        for alignment in rec.alignments:
            for hsp in alignment.hsps:
                hits.append(
                    {
                        "title": alignment.title,
                        "length": alignment.length,
                        "e_value": hsp.expect,
                        "bit_score": hsp.bits,
                        "identity": hsp.identities,
                        "align_length": hsp.align_length,
                        "query_start": hsp.query_start,
                        "identity_pct": round(hsp.identities / hsp.align_length * 100, 2)
                        if hsp.align_length
                        else 0,
                    }
                )

    hits = hits[:max_hits]
    if out_file:
        with open(out_file, "w") as f:
            f.write("query\tsubject\tevalue\tbitscore\tidentity%\n")
            for h in hits:
                f.write(
                    f"{query[:50]}\t{h['title']}\t{h['e_value']}\t"
                    f"{h['bit_score']}\t{h['identity_pct']}\n"
                )

    return json.dumps(
        {
            "mode": "remote",
            "program": program,
            "database": db,
            "hit_count": len(hits),
            "hits": hits[:50],
        },
        indent=2,
    )


def _blast_local(
    query: str,
    is_file: bool,
    program: str,
    subject: str,
    evalue: float,
    max_hits: int,
    out_file: str | None,
) -> str:
    if not subject:
        return json.dumps({"error": "Local BLAST needs 'database' (subject FASTA)."})
    blast_bin = _which_or_error(program)
    if not blast_bin:
        return json.dumps(
            {"error": f"{program} not found. Install blast+ (e.g. apt install ncbi-blast+)."}
        )
    makedb = _which_or_error("makeblastdb")
    if not makedb:
        return json.dumps({"error": "makeblastdb not found. Install blast+."})

    subj_path = _resolve_path(subject)
    db_prefix = subj_path + ".blastdb"

    # Build DB if not present
    if not os.path.exists(db_prefix + ".ndb" if makedb else db_prefix + ".nsq"):
        r = _run_cmd(
            [
                "makeblastdb",
                "-in",
                subj_path,
                "-dbtype",
                "nucl" if program in ("blastn", "tblastn", "tblastx") else "prot",
                "-out",
                db_prefix,
            ]
        )
        if r["returncode"] != 0:
            return json.dumps({"error": "makeblastdb failed", "stderr": r["stderr"]})

    query_path = query if is_file else None
    tmp_query = None
    if not query_path:
        tmp_query = tempfile.NamedTemporaryFile(mode="w", suffix=".fa", delete=False)
        tmp_query.write(f">query\n{query}\n")
        tmp_query.close()
        query_path = tmp_query.name

    cmd = [
        program,
        "-query",
        query_path,
        "-db",
        db_prefix,
        "-evalue",
        str(evalue),
        "-max_target_seqs",
        str(max_hits),
        "-outfmt",
        "6",
    ]
    r = _run_cmd(cmd)
    if tmp_query:
        os.unlink(tmp_query.name)

    if r["returncode"] != 0:
        return json.dumps({"error": f"{program} failed", "stderr": r["stderr"]})

    # Parse tabular output
    hits = []
    for line in r["stdout"].strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 12:
            hits.append(
                {
                    "query": parts[0],
                    "subject": parts[1],
                    "identity_pct": float(parts[2]),
                    "align_length": int(parts[3]),
                    "e_value": float(parts[10]),
                    "bit_score": float(parts[11]),
                }
            )

    if out_file:
        with open(out_file, "w") as f:
            f.write(r["stdout"])

    return json.dumps(
        {
            "mode": "local",
            "program": program,
            "subject": subject,
            "hit_count": len(hits),
            "hits": hits[:50],
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# bio_align — BWA / minimap2 / STAR wrapper
# ---------------------------------------------------------------------------


def align(args: dict, **kwargs) -> str:
    aligner = args.get("aligner", "")
    ref = args.get("reference", "")
    reads = args.get("reads", [])
    out_bam = args.get("output_bam", "")
    extra = args.get("extra_args", "")

    if not ref or not reads:
        return json.dumps({"error": "Need 'reference' and 'reads'."})
    ref_path = _resolve_path(ref)
    if not os.path.isfile(ref_path):
        return json.dumps({"error": f"Reference not found: {ref_path}"})
    if not out_bam:
        return json.dumps({"error": "Need 'output_bam'."})

    if aligner == "star":
        return json.dumps(
            {
                "error": "STAR alignment is complex (requires a genome index directory). "
                "Use the terminal tool to run STAR directly with appropriate --genomeDir.",
                "reference": ref_path,
                "reads": reads,
            }
        )

    read_args = [_resolve_path(r) for r in reads]
    for r in read_args:
        if not os.path.isfile(r):
            return json.dumps({"error": f"Read file not found: {r}"})

    mode = aligner if aligner in ("bwa-mem", "bwa", "minimap2") else "auto"
    mapper_kwargs = {}
    if extra:
        mapper_kwargs["extra_args"] = extra
    if aligner == "minimap2" and args.get("preset"):
        mapper_kwargs["preset"] = args["preset"]

    try:
        from hermes_bacmap.engine import ReadMapper

        result = ReadMapper.map(
            reads=read_args,
            reference=ref_path,
            out_bam=out_bam,
            mode=mode,
            **mapper_kwargs,
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Alignment failed: {e}"})


# ---------------------------------------------------------------------------
# bio_samtools — wrapper for common samtools operations
# ---------------------------------------------------------------------------


def samtools_op(args: dict, **kwargs) -> str:
    op = args.get("operation", "")
    inp = args.get("input", "")
    if not op or not inp:
        return json.dumps({"error": "Need 'operation' and 'input'."})

    samtools = _which_or_error("samtools")
    if not samtools:
        return json.dumps(
            {"error": "samtools not found. Install: conda install -c bioconda samtools"}
        )

    inp_path = _resolve_path(inp)
    if not os.path.isfile(inp_path):
        return json.dumps({"error": f"Input not found: {inp_path}"})

    output = args.get("output")
    output_path = _resolve_path(output) if output else None
    region = args.get("region", "")
    flags = args.get("flags", "")
    extra = args.get("extra_args", "")

    cmd: list[str] = ["samtools"]

    if op == "sort":
        if not output_path:
            return json.dumps({"error": "sort needs 'output'."})
        cmd += ["sort", "-@", str(os.cpu_count() or 4)]
        if extra:
            cmd += extra.split()
        cmd += ["-o", output_path, inp_path]
    elif op == "index":
        cmd += ["index", inp_path]
    elif op == "view":
        cmd += ["view"]
        if flags:
            cmd += flags.split()
        if extra:
            cmd += extra.split()
        if output_path:
            cmd += ["-o", output_path]
        cmd += [inp_path]
        if region:
            cmd.append(region)
    elif op == "depth":
        cmd += ["depth"]
        if region:
            cmd += ["-r", region]
        cmd += [inp_path]
    elif op == "flagstat":
        cmd += ["flagstat", inp_path]
    elif op == "idxstats":
        cmd += ["idxstats", inp_path]
    elif op == "mpileup":
        if not output_path:
            return json.dumps({"error": "mpileup needs 'output'."})
        cmd += ["mpileup", "-f", args.get("reference", ""), "-o", output_path, inp_path]
        if not args.get("reference"):
            return json.dumps({"error": "mpileup needs 'reference' FASTA."})
    elif op == "faidx" or op == "fasta_index":
        cmd += ["faidx", inp_path]
    else:
        return json.dumps({"error": f"Unknown operation: {op}"})

    r = _run_cmd(cmd)
    if r["returncode"] != 0:
        return json.dumps({"error": f"samtools {op} failed", "stderr": r["stderr"]})

    result: dict[str, Any] = {
        "operation": op,
        "input": inp,
        "output": output,
        "returncode": r["returncode"],
    }
    if r["stdout"].strip():
        # Truncate large stdout
        lines = r["stdout"].strip().split("\n")
        result["stdout"] = "\n".join(lines[:100])
        result["stdout_lines"] = len(lines)
    if r["stderr"].strip():
        result["stderr_tail"] = r["stderr"].strip().split("\n")[-3:]
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# bio_variant — variant calling / manipulation
# ---------------------------------------------------------------------------


def variant(args: dict, **kwargs) -> str:
    op = args.get("operation", "")
    inp = args.get("input", "")
    if not op:
        return json.dumps({"error": "Need 'operation'."})

    if op == "mpileup_call":
        return _var_mpileup_call(inp, args)
    elif op == "filter":
        return _var_filter(inp, args)
    elif op == "query":
        return _var_query(inp, args)
    elif op == "annotate":
        return _var_annotate(inp, args)
    elif op == "consensus":
        return _var_consensus(inp, args)
    return json.dumps({"error": f"Unknown operation: {op}"})


def _var_mpileup_call(inp: str, args: dict) -> str:
    bcftools = _which_or_error("bcftools")
    if not bcftools:
        return json.dumps(
            {"error": "bcftools not found. Install: conda install -c bioconda bcftools"}
        )
    samtools = _which_or_error("samtools")
    if not samtools:
        return json.dumps({"error": "samtools not found."})

    inp_path = _resolve_path(inp)
    ref = args.get("reference", "")
    if not ref:
        return json.dumps({"error": "mpileup_call needs 'reference' FASTA."})
    ref_path = _resolve_path(ref)
    output = args.get("output")
    if not output:
        return json.dumps({"error": "Need 'output' VCF path."})
    out_path = _resolve_path(output)
    extra = args.get("extra_args", "")

    # Index reference if needed
    if not os.path.exists(ref_path + ".fai"):
        subprocess.run(["samtools", "faidx", ref_path], capture_output=True, timeout=120)

    # Index BAM if needed
    if not os.path.exists(inp_path + ".bai"):
        subprocess.run(["samtools", "index", inp_path], capture_output=True, timeout=120)

    mpileup_cmd = [
        "bcftools",
        "mpileup",
        "-f",
        ref_path,
        inp_path,
    ]
    if extra:
        mpileup_cmd += extra.split()
    call_cmd = ["bcftools", "call", "-mv", "-Ov"]

    # Pipe: mpileup | call > output
    p1 = subprocess.Popen(mpileup_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with open(out_path, "wb") as f:
        p2 = subprocess.run(
            call_cmd, stdin=p1.stdout, stdout=f, stderr=subprocess.PIPE, timeout=600
        )
    p1.stdout.close()
    err = p1.stderr.read().decode() + p2.stderr.decode()

    if p1.wait() != 0 or p2.returncode != 0:
        return json.dumps({"error": "bcftools mpileup/call failed", "stderr": err[-2000:]})

    return json.dumps(
        {
            "operation": "mpileup_call",
            "input_bam": inp,
            "reference": ref,
            "output_vcf": out_path,
            "variant_count": _count_vcf_records(out_path),
        }
    )


def _var_filter(inp: str, args: dict) -> str:
    bcftools = _which_or_error("bcftools")
    if not bcftools:
        return json.dumps({"error": "bcftools not found."})
    inp_path = _resolve_path(inp)
    if not os.path.isfile(inp_path):
        return json.dumps({"error": f"VCF not found: {inp_path}"})
    output = args.get("output", inp_path + ".filtered.vcf")
    out_path = _resolve_path(output)
    expr = args.get("filter_expr", "")
    if not expr:
        return json.dumps({"error": "Need 'filter_expr' (e.g. 'QUAL>30 && DP>10')"})
    extra = args.get("extra_args", "")

    cmd = ["bcftools", "filter", "-i", expr, "-o", out_path, inp_path]
    if extra:
        cmd += extra.split()
    r = _run_cmd(cmd)
    if r["returncode"] != 0:
        return json.dumps({"error": "bcftools filter failed", "stderr": r["stderr"]})

    return json.dumps(
        {
            "operation": "filter",
            "input": inp,
            "output": out_path,
            "filter_expr": expr,
            "input_variants": _count_vcf_records(inp_path),
            "filtered_variants": _count_vcf_records(out_path),
        }
    )


def _var_query(inp: str, args: dict) -> str:
    bcftools = _which_or_error("bcftools")
    if not bcftools:
        return json.dumps({"error": "bcftools not found."})
    inp_path = _resolve_path(inp)
    if not os.path.isfile(inp_path):
        return json.dumps({"error": f"VCF not found: {inp_path}"})
    qfmt = args.get("query", "%CHROM\\t%POS\\t%REF\\t%ALT\\t%QUAL\\n")
    extra = args.get("extra_args", "")

    cmd = ["bcftools", "query", "-f", qfmt, inp_path]
    if extra:
        cmd += extra.split()
    r = _run_cmd(cmd)
    if r["returncode"] != 0:
        return json.dumps({"error": "bcftools query failed", "stderr": r["stderr"]})

    lines = r["stdout"].strip().split("\n") if r["stdout"].strip() else []
    return json.dumps(
        {
            "operation": "query",
            "input": inp,
            "format": qfmt,
            "record_count": len(lines),
            "results": lines[:200],
        }
    )


def _var_annotate(inp: str, args: dict) -> str:
    bcftools = _which_or_error("bcftools")
    if not bcftools:
        return json.dumps({"error": "bcftools not found."})
    inp_path = _resolve_path(inp)
    if not os.path.isfile(inp_path):
        return json.dumps({"error": f"VCF not found: {inp_path}"})
    output = args.get("output", inp_path + ".annotated.vcf")
    out_path = _resolve_path(output)
    extra = args.get("extra_args", "")

    cmd = ["bcftools", "annotate", "-o", out_path, inp_path]
    if extra:
        cmd += extra.split()
    r = _run_cmd(cmd)
    if r["returncode"] != 0:
        return json.dumps({"error": "bcftools annotate failed", "stderr": r["stderr"]})

    return json.dumps(
        {
            "operation": "annotate",
            "input": inp,
            "output": out_path,
        }
    )


def _var_consensus(inp: str, args: dict) -> str:
    bcftools = _which_or_error("bcftools")
    if not bcftools:
        return json.dumps({"error": "bcftools not found."})
    inp_path = _resolve_path(inp)
    ref = args.get("reference", "")
    if not ref:
        return json.dumps({"error": "consensus needs 'reference' FASTA."})
    ref_path = _resolve_path(ref)
    output = args.get("output")
    if not output:
        return json.dumps({"error": "Need 'output' FASTA path."})
    out_path = _resolve_path(output)
    extra = args.get("extra_args", "")

    # Index reference if needed
    if not os.path.exists(ref_path + ".fai"):
        subprocess.run(["samtools", "faidx", ref_path], capture_output=True, timeout=120)

    cmd = ["bcftools", "consensus", "-f", ref_path, inp_path]
    if extra:
        cmd += extra.split()
    with open(out_path, "w") as f:
        proc = subprocess.run(cmd, stdout=f, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        return json.dumps({"error": "bcftools consensus failed", "stderr": proc.stderr})

    return json.dumps(
        {
            "operation": "consensus",
            "input_vcf": inp,
            "reference": ref,
            "output_fasta": out_path,
        }
    )


def _count_vcf_records(path: str) -> int:
    """Count non-header, non-empty lines in a VCF."""
    if not os.path.isfile(path):
        return 0
    count = 0
    with open(path) as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                count += 1
    return count


# ---------------------------------------------------------------------------
# High-level analysis tools (project.md §7 Salmonella pipeline)
# ---------------------------------------------------------------------------


def analyze_salmonella(args: dict, **kwargs) -> str:
    """Trigger full analysis pipeline via Snakemake.
    Works for Salmonella, DEC, Shigella, EIEC — species routing is automatic
    via three-gene identification (invA/uidA/ipaH)."""
    sample_id = args.get("sample_id", "")
    cores = args.get("cores", 8)

    _run_project_script("run_analysis.py", ["--sample", sample_id, "--cores", str(cores)])

    summary_path = _RESULTS_DIR / sample_id / "report" / f"{sample_id}_summary.json"
    if summary_path.exists():
        with summary_path.open() as f:
            return f.read()
    return json.dumps({"error": "Pipeline completed but summary not found"})


def get_result(args: dict, **kwargs) -> str:
    """Retrieve analysis summary for a completed sample."""
    sample_id = args.get("sample_id", "")
    summary_path = _RESULTS_DIR / sample_id / "report" / f"{sample_id}_summary.json"

    if not summary_path.exists():
        return json.dumps(
            {"error": f"No results found for {sample_id}. Run bio_analyze_salmonella first."}
        )

    with summary_path.open() as f:
        summary = json.load(f)

    steps = summary.get("steps", {})

    sp = steps.get("species", {})
    verdict = sp.get("verdict", "N/A") if isinstance(sp, dict) else str(sp)

    mlst_raw = steps.get("mlst", "")
    st = "N/A"
    if mlst_raw:
        lines = mlst_raw.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[-1].split("\t")
            if len(parts) >= 3:
                st = parts[2]

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


def verify_result(args: dict, **kwargs) -> str:
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
        return json.dumps({"error": f"Verifier failed: {e}"})


def generate_report(args: dict, **kwargs) -> str:
    """Generate HTML report for a sample."""
    sample_id = args.get("sample_id", "")
    _run_project_script("generate_report.py", ["--sample", sample_id], timeout=60)
    report_path = _RESULTS_DIR / sample_id / "report" / f"{sample_id}_report.html"
    if report_path.exists():
        return json.dumps({"sample_id": sample_id, "report_path": str(report_path)})
    return json.dumps({"error": "Report generation failed"})


def list_samples(args: dict, **kwargs) -> str:
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


def gene_scan(args: dict, **kwargs) -> str:
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
        return json.dumps({"error": f"gene_scan failed: {e}"})


def vpa_serotype(args: dict, **kwargs) -> str:
    """Predict V. parahaemolyticus O/K serotype from contigs."""
    contigs_path = args.get("contigs_path", "")
    sample_id = args.get("sample_id", "")

    contigs = Path(contigs_path)
    if not contigs.exists():
        return json.dumps({"error": f"Contigs not found: {contigs_path}"})

    if not sample_id:
        sample_id = contigs.parent.parent.name

    try:
        import sys

        sys.path.insert(0, str(_PROJECT_ROOT / "src"))
        from hermes_bacmap.typing.vpa_serotyper import VpaSerotyper

        serotyper = VpaSerotyper()
        result = serotyper.analyze(contigs_path, sample_id)
        return json.dumps(result.to_dict(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"VPA serotyping failed: {e}"})


def query_metadata(args: dict, **kwargs) -> str:
    """Query strain background metadata."""
    db_path = _DEFAULT_DB_PATH
    if not db_path.exists():
        return json.dumps({"error": "Database not found. Run analysis first."})

    try:
        import sys

        sys.path.insert(0, str(_PROJECT_ROOT / "src"))
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
        return json.dumps({"error": f"Query failed: {e}"})


def add_metadata(args: dict, **kwargs) -> str:
    """Add or update strain background metadata."""
    strain_id = args.get("strain_id", "")
    data = args.get("data", {})

    if not strain_id:
        return json.dumps({"error": "strain_id is required"})
    if not data or not isinstance(data, dict):
        return json.dumps({"error": "data dict is required"})

    db_path = _DEFAULT_DB_PATH

    try:
        import sys

        sys.path.insert(0, str(_PROJECT_ROOT / "src"))
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
        return json.dumps({"error": f"Add metadata failed: {e}"})


def query_lab_results(args: dict, **kwargs) -> str:
    """Query wet lab experiment results."""
    db_path = _DEFAULT_DB_PATH
    if not db_path.exists():
        return json.dumps({"error": "Database not found."})

    try:
        import sys

        sys.path.insert(0, str(_PROJECT_ROOT / "src"))
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
                search_kwargs: dict = {}
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
        return json.dumps({"error": f"Query failed: {e}"})


def add_lab_result(args: dict, **kwargs) -> str:
    """Record a wet lab experiment result."""
    strain_id = args.get("strain_id", "")
    category = args.get("category", "")
    test_name = args.get("test_name", "")
    result = args.get("result", "")

    if not all([strain_id, category, test_name, result]):
        return json.dumps({"error": "strain_id, category, test_name, result are required"})

    db_path = _DEFAULT_DB_PATH

    try:
        import sys

        sys.path.insert(0, str(_PROJECT_ROOT / "src"))
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
        return json.dumps({"error": f"Add lab result failed: {e}"})


def snp_tree(args: dict, **kwargs) -> str:
    """Retrieve cohort-level SNP phylogenetic tree and distance matrix."""
    db_path = _DEFAULT_DB_PATH
    if db_path.exists():
        try:
            from hermes_bacmap.services.genome_object_service import GenomeObjectService, ObjectType

            with GenomeObjectService(db_path) as gos:
                cohort_objs = [
                    o
                    for o in gos.list_by_type(ObjectType.ANALYSIS)
                    if o.strain_id and o.strain_id.startswith("cohort:") and o.strain_id.endswith("-snp")
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
            pass

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
        return json.dumps({"error": f"Failed to read SNP summary: {e}"})


def search_samples(args: dict, **kwargs) -> str:
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
                        k: v for k, v in {
                            "serotype": serotype,
                            "mlst_st": mlst_st,
                            "amr_gene": amr_gene,
                            "organism": organism,
                        }.items() if v
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
            return json.dumps({"error": "Provide at least one of: query, serotype, mlst_st, amr_gene, organism"})

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
                if obj.strain_id in seen or obj.strain_id.startswith("cohort:"):
                    continue
                seen.add(obj.strain_id)

                p = obj.payload
                sero = p.get("serotype", {})
                serovar = sero.get("sistr", "") if isinstance(sero, dict) else ""

                mlst_raw = p.get("mlst", "")
                st_val = ""
                if mlst_raw and isinstance(mlst_raw, str):
                    parts = mlst_raw.strip().split("\t")
                    if len(parts) >= 3:
                        st_val = parts[2]

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

                matches.append({
                    "strain_id": obj.strain_id,
                    "organism": obj.organism,
                    "serotype": serovar or "N/A",
                    "mlst_st": f"ST{st_val}" if st_val else "N/A",
                    "amr_genes": sorted(set(amr_genes))[:20],
                    "matched_fields": reasons[:3],
                })

            return json.dumps(
                {"query": query, "count": len(matches), "results": matches[:limit]},
                ensure_ascii=False,
            )
    except Exception as e:
        return json.dumps({"error": f"Search failed: {e}"})


def annotate_genome(args: dict, **kwargs) -> str:
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
        return json.dumps({"error": f"Annotation failed: {e}"})


def diagnose_failure(args: dict, **kwargs) -> str:
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
