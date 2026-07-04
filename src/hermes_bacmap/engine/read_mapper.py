from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .registry import Registry

_REG = Registry()
_BUILTINS: dict[str, tuple[str, str]] = {}

_PIXI_BIN = str(Path(__file__).resolve().parents[2] / ".pixi" / "envs" / "default" / "bin")


def _pixi_path() -> str:
    return f"{_PIXI_BIN}:{os.environ.get('PATH', '')}"


def _which(name: str) -> str | None:
    return shutil.which(name, path=_pixi_path())


def _ensure_bwa_index(ref: str) -> None:
    if not Path(ref + ".bwt").exists():
        bwa = _which("bwa")
        if not bwa:
            raise RuntimeError("bwa not found")
        subprocess.run([bwa, "index", ref], capture_output=True, timeout=120)


def _sort_and_index(sam_stdout: str, out_bam: str, threads: int) -> None:
    samtools = _which("samtools")
    if not samtools:
        raise RuntimeError("samtools not found")

    proc = subprocess.run(
        [samtools, "sort", "-@", str(threads), "-o", out_bam, "-"],
        input=sam_stdout,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"samtools sort failed: {proc.stderr[:500]}")

    subprocess.run([samtools, "index", out_bam], capture_output=True, timeout=120)


class BwaReadMapper:
    def map(self, reads: list[str], reference: str, out_bam: str, **kwargs) -> dict:
        threads = kwargs.get("threads", os.cpu_count() or 4)
        extra = kwargs.get("extra_args", "")

        _ensure_bwa_index(reference)

        bwa = _which("bwa")
        if not bwa:
            raise RuntimeError("bwa not found")

        cmd = [bwa, "mem", "-t", str(threads)]
        if extra:
            cmd += extra.split()
        cmd += [reference] + reads

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"bwa mem failed: {proc.stderr[:500]}")

        _sort_and_index(proc.stdout, out_bam, threads)

        return {
            "aligner": "bwa-mem",
            "reference": reference,
            "reads": reads,
            "output_bam": out_bam,
            "paired_end": len(reads) == 2,
            "indexed": Path(out_bam + ".bai").exists(),
        }


class Minimap2ReadMapper:
    def map(self, reads: list[str], reference: str, out_bam: str, **kwargs) -> dict:
        threads = kwargs.get("threads", os.cpu_count() or 4)
        preset = kwargs.get("preset", "map-ont")
        extra = kwargs.get("extra_args", "")

        mm2 = _which("minimap2")
        if not mm2:
            raise RuntimeError("minimap2 not found")

        cmd = [mm2, "-ax", preset, "--secondary=no", "-Y", "-t", str(threads)]
        if extra:
            cmd += extra.split()
        cmd += [reference] + reads

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"minimap2 failed: {proc.stderr[:500]}")

        _sort_and_index(proc.stdout, out_bam, threads)

        return {
            "aligner": "minimap2",
            "preset": preset,
            "reference": reference,
            "reads": reads,
            "output_bam": out_bam,
            "indexed": Path(out_bam + ".bai").exists(),
        }


_BUILTINS["bwa"] = ("__main__", "BwaReadMapper")
_BUILTINS["bwa-mem"] = ("__main__", "BwaReadMapper")
_BUILTINS["minimap2"] = ("__main__", "Minimap2ReadMapper")


def _get_mapper(name: str):
    key = name.strip().lower()
    if key in ("bwa", "bwa-mem"):
        return BwaReadMapper()
    if key == "minimap2":
        return Minimap2ReadMapper()
    raise KeyError(f"Unknown read mapper: {name}")


class ReadMapper:
    """Map sequencing reads to a reference genome, producing sorted BAM."""

    @classmethod
    def map(
        cls,
        reads: list[str],
        reference: str,
        out_bam: str,
        mode: str = "auto",
        **kwargs,
    ) -> dict:
        if mode == "auto":
            mode = cls._select(reads)
        mapper = _get_mapper(mode)
        return mapper.map(reads, reference, out_bam, **kwargs)

    @staticmethod
    def _select(reads: list[str]) -> str:
        for r in reads:
            if r.endswith((".fasta", ".fa", ".fna")):
                return "minimap2"
        return "bwa"
