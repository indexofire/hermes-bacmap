import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


WORKFLOW_DIR = ROOT / "workflows" / "bacmap"
SAMPLES_TSV = WORKFLOW_DIR / "config" / "samples.tsv"

_SAMPLE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_sample_name(name: str) -> None:
    """Reject sample names that could break shell-concatenated Snakemake commands.

    snp.smk builds shell strings by interpolating sample names; a name with
    shell metacharacters (space, ;, $, backtick, etc.) would allow command
    injection. Allow only the safe identifier charset used by real sample IDs.
    """
    if not _SAMPLE_NAME_RE.match(name):
        raise ValueError(
            f"unsafe sample name {name!r}: must match ^[A-Za-z0-9._-]+$ "
            "(shell metacharacters are rejected to prevent command injection "
            "in Snakemake rules)"
        )


def validate_all_sample_names() -> list[str]:
    """Load samples.tsv and validate every name. Returns the list of names."""
    if not SAMPLES_TSV.exists():
        print(f"❌ samples.tsv not found: {SAMPLES_TSV}")
        sys.exit(1)
    with SAMPLES_TSV.open() as f:
        names = [r["sample"] for r in csv.DictReader(f, delimiter="\t")]
    for name in names:
        validate_sample_name(name)
    return names
