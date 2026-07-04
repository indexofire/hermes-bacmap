from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..hits import Hit

_BLAST_OUTFMT = (
    "6 qseqid sseqid pident length mismatch gapopen "
    "qstart qend sstart send evalue bitscore qlen slen"
)

_PARAM_MAP = {
    "pident": "perc_identity",
    "perc_identity": "perc_identity",
    "qcovs": "qcov_hsp_perc",
    "qcov_hsp_perc": "qcov_hsp_perc",
    "threads": "num_threads",
    "num_threads": "num_threads",
    "evalue": "evalue",
    "max_targets": "max_target_seqs",
    "max_target_seqs": "max_target_seqs",
}

_PIXI_BIN = str(Path(__file__).resolve().parents[4] / ".pixi" / "envs" / "default" / "bin")


class BlastBackend:
    """BLAST+ backend supporting blastn, blastp, blastx, tblastn, tblastx."""

    def __init__(self, tool: str = "blastn", threads: int = 4):
        self.tool = tool
        self.threads = threads
        self._bin = self._find_binary()

    def _find_binary(self) -> str:
        import os
        path = f"{_PIXI_BIN}:{os.environ.get('PATH', '')}"
        binary = shutil.which(self.tool, path=path)
        if not binary:
            raise RuntimeError(f"{self.tool} not found in PATH")
        return binary

    def make_db(
        self, fasta_file: Path, db_path: Path, db_type: str = "nucl"
    ) -> None:
        makeblastdb = shutil.which("makeblastdb", path=_PIXI_BIN) or shutil.which("makeblastdb")
        if not makeblastdb:
            raise RuntimeError("makeblastdb not found")
        cmd = [makeblastdb, "-in", str(fasta_file), "-dbtype", db_type, "-out", str(db_path)]
        subprocess.run(cmd, check=True, capture_output=True)

    def ensure_index(self, db_prefix: str, db_type: str = "nucl") -> None:
        ext = ".phr" if db_type == "prot" else ".nhr"
        if not Path(f"{db_prefix}{ext}").exists():
            fasta_candidates = [
                Path(f"{db_prefix}.fasta"),
                Path(f"{db_prefix}_sequences.fasta"),
                Path(f"{db_prefix}_abricate.fasta"),
            ]
            for fc in fasta_candidates:
                if fc.exists():
                    self.make_db(fc, Path(db_prefix), db_type)
                    return
            raise FileNotFoundError(f"No BLAST index or source FASTA for {db_prefix}")

    def find(
        self,
        query: Path,
        db_path: str,
        min_identity: float = 0.0,
        min_coverage: float = 0.0,
        evalue: float = 1e-5,
        max_targets: int = 500,
        **kwargs,
    ) -> list[Hit]:
        cmd = [
            self._bin,
            "-query", str(query),
            "-db", db_path,
            "-outfmt", _BLAST_OUTFMT,
            "-evalue", str(evalue),
            "-max_target_seqs", str(max_targets),
            "-num_threads", str(self.threads),
        ]

        for key, value in kwargs.items():
            if value is None or key in ("num_threads", "threads"):
                continue
            mapped = _PARAM_MAP.get(key, key)
            if isinstance(value, bool):
                if value:
                    cmd.append(f"-{mapped}")
            else:
                cmd.extend([f"-{mapped}", str(value)])

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"{self.tool} failed (exit {proc.returncode}): {proc.stderr.strip()[:500]}"
            )

        hits: list[Hit] = []
        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                hit = Hit.from_blast_line(line)
            except ValueError:
                continue
            if hit.identity >= min_identity and hit.query_coverage >= min_coverage:
                hits.append(hit)

        return hits


class MinimapBackend:
    """minimap2 backend for assembly-to-reference alignment."""

    def __init__(self, preset: str = "asm5", threads: int = 4):
        self.preset = preset
        self.threads = threads
        self._bin = self._find_binary()

    def _find_binary(self) -> str:
        import os
        path = f"{_PIXI_BIN}:{os.environ.get('PATH', '')}"
        binary = shutil.which("minimap2", path=path)
        if not binary:
            raise RuntimeError("minimap2 not found in PATH")
        return binary

    def find(
        self,
        query: Path,
        target: Path,
        min_identity: float = 0.0,
        min_coverage: float = 0.0,
        preset: Optional[str] = None,
        **kwargs,
    ) -> list[Hit]:
        use_preset = preset or self.preset
        cmd = [
            self._bin,
            "-x", use_preset,
            "-t", str(self.threads),
            "-c",
            "--secondary=no",
            str(target),
            str(query),
        ]

        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f"-{key}", str(value)])

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"minimap2 failed (exit {proc.returncode}): {proc.stderr.strip()[:500]}"
            )

        hits: list[Hit] = []
        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                hit = Hit.from_paf_line(line)
            except ValueError:
                continue
            if hit.identity >= min_identity and hit.subject_coverage >= min_coverage:
                hits.append(hit)

        return hits
