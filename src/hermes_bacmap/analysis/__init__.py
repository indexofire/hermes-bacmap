"""Analysis algorithms: gene scanning, species ID, taxonomy, annotation, verification."""

from .deterministic_verifier import CheckResult, DeterministicVerifier, VerificationResult
from .failure_diagnostics import Diagnosis, diagnose, diagnose_from_log
from .gene_identity import normalize_amr
from .gene_scanner import GeneHit, ScanResult, scan, scan_multi
from .genome_annotator import AnnotationResult, Feature, annotate
from .nli_reflector import extract_facts, reflect
from .nli_types import AtomicClaim, ClaimType, ClaimVerdict, ReflectionResult, StrainFacts, Verdict
from .species_canon import (
    ECOLI,
    SALMONELLA,
    SHIGELLA,
    VPARA,
    canonical_from_verdict,
    collapse_binomial,
)
from .species_identifier import SpeciesIdResult, identify
from .taxonomic_validator import TaxonomyResult, validate_genome

__all__ = [
    "AnnotationResult",
    "AtomicClaim",
    "CheckResult",
    "ClaimType",
    "ClaimVerdict",
    "DeterministicVerifier",
    "Diagnosis",
    "ECOLI",
    "Feature",
    "GeneHit",
    "ReflectionResult",
    "SALMONELLA",
    "ScanResult",
    "SHIGELLA",
    "SpeciesIdResult",
    "StrainFacts",
    "TaxonomyResult",
    "VerificationResult",
    "Verdict",
    "VPARA",
    "annotate",
    "canonical_from_verdict",
    "collapse_binomial",
    "diagnose",
    "diagnose_from_log",
    "extract_facts",
    "identify",
    "normalize_amr",
    "reflect",
    "scan",
    "scan_multi",
    "validate_genome",
]
