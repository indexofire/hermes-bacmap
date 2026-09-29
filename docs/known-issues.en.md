# Known Issues

> **Last updated**: 2026-09-07
> **Test status**: 1415 passed, 0 failed
> **Source**: code audit Rounds 1-9 (58 bugs fixed)

---

## 🟠 Medium — Defensive improvements

### M1. (Completed — MinimapBackend kwargs parameter mapping + bool handling)

- **Location**: `src/hermes_bacmap/engine/backends/minimap2.py`
- **Problem**: The kwargs loop in `MinimapBackend.find()` naively joins every key-value pair as
  `-key value`, with no parameter mapping table (`_PARAM_MAP`), no bool handling, and no
  skip-None. If the caller passes `c=True`, it generates `-c True` (wrong — should be `-c`).
- **Fix** (2026-07-18): Followed the `BlastBackend.find()` pattern — added `_PARAM_MAP` (pythonic
  names → minimap2 short options), bool True generates a bare flag, bool False/None are skipped,
  and the `threads` kwarg replaces any existing `-t` value instead of appending. Added 4 unit
  tests for coverage.

### M2. (Completed — ReadMapper long-read routing)

- **Location**: `src/hermes_bacmap/engine/read_mapper.py`
- **Problem**: `_select()` only checks the FASTA extension to decide whether to use minimap2. All FASTQ (including ONT/PacBio long reads) defaults to BWA-MEM, with poor performance.
- **Fix** (2026-07-18): `ReadMapper.map()` gained a `read_type` parameter ("short"/"long"); when
  `read_type` is omitted, the first ~100 FASTQ records are auto-sniffed (≥1000bp counts as long
  reads, .gz supported, falls back to short on failure); the `bio_align` tool schema exposes
  `read_type` in sync.

### M3. (Completed — SAM pipeline streaming)

- **Location**: `src/hermes_bacmap/engine/read_mapper.py`
- **Problem**: The full SAM output of `bwa mem` / `minimap2` is read into `proc.stdout` (Python str), then passed to `samtools sort`. For 50× WGS samples the SAM can reach 5-10GB, posing an OOM risk.
- **Fix** (2026-07-18): Added `_run_align_and_sort()`: aligner stdout connects directly to
  `samtools sort` stdin via a `Popen` pipe with zero full buffering; aligner stderr goes to a
  temp file to avoid pipe deadlock and is raised with the exception on failure. Smoke-verified
  with real bwa/minimap2.

---

## 🟡 Low — Cosmetic / edge cases

### L1. (Completed — Added .fna/.fa candidate extensions)

- **Location**: `src/hermes_bacmap/engine/backends/blast.py:50-56`
- **Problem**: When the BLAST index is missing, `ensure_index()` tries to rebuild from FASTA with candidate extensions `.fasta`, `_sequences.fasta`, `_abricate.fasta` — missing `.fna` and `.fa`.
- **Current impact**: None. Existing databases all use the `_sequences.fasta` or `_abricate.fasta` suffixes.
- **Proposed fix**: Add `.fna`, `.fa`, `.fna.gz`, etc. to the candidate list.

### L2. (Completed — available() merges dynamically registered backends)

- **Location**: `src/hermes_bacmap/engine/backends/__init__.py:42-43`
- **Problem**: `available()` returns `_BUILTINS.keys()` (hardcoded built-in backend names) and does not reflect custom backends registered dynamically via `register()`.
- **Current impact**: None. No custom backends are currently registered.
- **Proposed fix**: Merge `_BUILTINS.keys()` and `_REG.available().keys()`.

### L3. (Completed — 2>/dev/null cleaned up)

- **Location**: `workflows/bacmap/rules/snp.smk` (multiple shell blocks)
- **Problem**: stderr from `bwa mem`, `bcftools mpileup/call`, and `bcftools reheader/view/index` is all discarded via `2>/dev/null`. No diagnostic information when tools fail.
- **Current impact**: When the SNP pipeline fails, Snakemake shows only "Error code 1" with no stderr output.
- **Proposed fix**: Change `2>/dev/null` to `2>{log}` to write into a log file, or remove it entirely and let Snakemake capture it.
- **Priority**: Medium. Handle together with the next snp.smk change.

### L4. (Completed — All E501 long lines fixed)

- **Location**: `deterministic_verifier.py`, `ecoh_serotyper.py`, `gene_scanner.py`, `genome_annotator.py`, `genome_object_service.py`, `schemas.py`, `shigella_serotyper.py`, `tools.py`
- **Problem**: 19 lines exceed 100 characters (ruff E501); 12 files do not conform to ruff format.
- **Current impact**: Purely cosmetic; no runtime impact.
- **Proposed fix**: `ruff format src/hermes_bacmap/ && ruff check --fix src/hermes_bacmap/`

### L5. (Completed — annotation added to rule all)

- **Location**: `workflows/bacmap/Snakefile:rule all`
- **Problem**: `rule all` includes the per-sample summary + SNP cohort summary but not `{sample}/annotation/annotation.json`. The annotation rule exists and works but must be triggered separately.
- **Current impact**: `snakemake` or `run_analysis.py --all` does not run annotation automatically.
- **Proposed fix**: Add `expand(str(WORKDIR) + "/{sample}/annotation/annotation.json", sample=SAMPLES)` to the `rule all` input.
- **Priority**: Decide after determining whether annotation is a mandatory step for all samples.

### L6. (Completed — All sys.path.insert calls removed)

- **Location**: `src/hermes_bacmap/tools.py` (5 occurrences: lines 798, 1203, 1272, 1300, 1358)
- **Problem**: Several tool handlers internally use `sys.path.insert(0, str(_PROJECT_ROOT / "src"))` to import hermes_bacmap modules. This is a runtime path modification and is not clean.
- **Current impact**: No functional issues. But if hermes_bacmap is already on the path in the Hermes environment, the insert is redundant.
- **Proposed fix**: Do a single `sys.path.insert` at the top of `tools.py`, or ensure the module is already on the path via the plugin mechanism.

---

## Architectural decisions pending

### A1. (Completed — V.para serotyping implemented)

- **Status**: ✅ Completed (VpaSerotyper, ported from vpautils)
- **Reference**: docs/architecture/engine.md (engine layer MashBackend/SourmashBackend)

### A2. GBrain embedding pending configuration (blocked — ollama not installed)

- **Status**: GBrain v0.42.57.0 installed, PGLite initialized, 10 pages imported
- **Blocked** (assessed 2026-07-18): `~/.local/bin/ollama` is a stale file containing "Not Found"
  (a placeholder from a failed download); ollama is not actually installed; embedding requires a
  working ollama service (`nomic-embed-text`). Installing ollama is a system-level change,
  pending user decision
- **Docs**: `docs/architecture/gbrain.md`

### A3. (Completed — AMRFinderPlus integration)

- **Status**: ✅ Completed 2026-07-18. pixi installs `ncbi-amrfinderplus 3.12` (4.x libcurl/libzlib conflicts with the existing environment);
  `typing_amr.smk` gained an `amr_amrfinderplus` rule (maps --organism by sample species; omitted for V.para which has no corresponding organism);
  `report.smk` + `collect_summary.py` consume `steps.amr.amrfinderplus`; the `run_analysis.py --status` interpretation already consumed this field

### A3. R ggtree visualization environment (won't fix — keep documented workaround)

- **Status**: pixi solver conflicts with existing dependencies; system R 4.6 cpp11 incompatible; no conda/mamba on this machine
- **Assessment** (2026-07-18): purely for visualization and `generate_report.py` already has a
  text fallback tree, so the cost/benefit is low. Keep the workaround:
  `conda create -n r-viz -c bioconda -c conda-forge r-base=4.4 r-ggplot2 bioconductor-ggtree`,
  pending user decision

### A4. (Partially completed — DAG dry-run + web smoke tests in CI)

- **Status**: ✅ 2026-07-18 added a `snakemake-dag` CI job (pip installs snakemake 7.32 + dummy
  reads; `snakemake -n` builds a 179-job DAG) and 13 FastAPI TestClient smoke tests;
  `_vpa_genes` has RIMD O3:K6 end-to-end tests (5)
- **Remaining**: a full Snakemake execution test with real data (needs gold_standard FASTQ, too large; not in CI for now)

### A5. Tool renaming (closed — no residue)

- **Status**: ✅ Closed after review on 2026-09-07. No `bio_analyze_salmonella` residue remains
  in the codebase (the only hit is a historical CHANGELOG.md entry, which is normal history); the
  current name `bio_analyze_pathogen` is registered in `tools/registry.py` with the schema in
  sync. No further renaming needed.

---

## 🟠 B series — Found in the V0.7 benchmark round (2026-09-07)

### B1. Full benchmark timing unstable on this machine (low-depth assembly × oversubscribed concurrency)

- **Location**: `scripts/benchmark_batch.py run` (AMD Ryzen 7 5700G, 8c/16t)
- **Problem**: 150k-read downsampled samples occasionally fail at assembly/qc under cores=15
  (4× fastp --thread 8 oversubscribed) or low-coverage pilon correction
  (coverage 7 on the edge of minDepth 5), so a single clean full timing run cannot complete;
  incremental reruns at cores=8 are stable.
- **Current impact**: the benchmark extrapolation is based on piecewise conservative synthetic
  timing (annotated in `bench_timing.json.timing_source`); production full-depth data is
  unaffected (coverage far above the downsampling).
- **Proposed fix**: re-test on recommended-tier hardware; or raise bench samples to ≥300k reads
  + rule-level threads/resource declarations (snakemake resources mem_mb constraint,
  project.md §11.3).
- **Priority**: Medium (V0.8 candidate).

### B2. .smk f-string params path-space bug (✅ Fixed 2026-09-07)

- **Location**: `species.smk` / `vpara.smk` / `dec_shigella.smk` / `annotation.smk`
- **Problem**: f-string lambdas of the form `params: out = lambda wc: str(WORKDIR) + f"/{wc.sample}/..."`
  expand into space-containing paths under snakemake 7.32 shell format
  (`out / SAMPLE /x.json`); both the python -c and fallback redirections fail —
  the bug never surfaced after the rule refactoring introduced it (production artifacts were all
  generated by the old rules, and unchanged timestamps prevented reruns).
- **Fix**: all 10 f-string lambdas changed to static template strings
  `str(WORKDIR) + "/{sample}/..."` (format semantics verified with a mini-Snakefile);
  the V0.7 benchmark forced a full rerun as regression verification (before the fix, 7/68
  cascading failures → after the fix, 4/4 passed).
- **Lesson**: after rule refactoring, force a rerun (touch inputs or a full bench run) for
  regression; relying on timestamps alone masks shell-level defects.

### B3. Missing species_markers BLAST index + fallback writing invalid JSON (✅ Fixed 2026-09-07)

- **Location**: `data/reference/species/` indexes; `species.smk`/`dec_shigella.smk`/`vpara.smk` fallback parameters
- **Problem**: (1) the `species_markers` BLAST index is not in the repository (same class as the
  shigella_ref/ecoh findings from the bench round), so after the f-string fix the first real
  execution of the `species_identify` python hit FileNotFoundError;
  (2) the fallback parameters were written as `'{{...}}'`, and after snakemake 7.32 shell format
  the **double curly braces pass through verbatim**, writing invalid JSON to disk
  (`{{"species":...}}`) — a mini-Snakefile experiment confirmed single curly braces are the
  correct form, so the original escaping assumption was wrong from the day it was introduced.
- **Fix**: rebuilt the index with `gene_scanner.setup_db('species_markers')`; changed 4
  fallbacks to single curly braces (species ×1 / dec_shigella ×2 / vpara ×1). ECO-011 rerun
  verified: uidA 100%/100% → correct DEC routing.
- **P1 landed (2026-09-08)**: `_find_db` now implements **lazy index rebuild on missing index**
  (auto `setup_db` as a fallback when the index is missing; an enhanced error is raised only
  when the source FASTA is also absent) — the fresh-clone recurrence path is closed (locked by
  2 unit tests).
- **Lesson**: `|| echo fallback` is an error-fallback path and itself needs test coverage —
  an invalid-JSON fallback is more dangerous than a crash (downstream degrades silently).
  Index-type resources now self-heal via the lazy rebuild; CI validation will be revisited
  once an environment with the blast binary is available.

### B4. SAM-MCR-010 R2 FASTQ corruption (✅ Fixed 2026-09-07)

- **Problem**: the R2 downloaded in the V0.2 era was corrupted (gzip unexpected EOF, truncated
  at 60.8MB); the CHANGELOG once noted "R2 download corrupted, fix pending".
- **Fix**: re-downloaded with aria2c using 8-thread resumable transfer (ENA ERR2594882_2); MD5
  matches the ENA reported value (`8f4dec3005a04f556a1f3ae7b6429ce6`); gzip -t passes;
  537,706 records.
- **Note**: the pipeline rerun completed (Salmonella/invA ✅, Typhimurium ✅, mcr-1 ✅); MLST
  called ST19, inconsistent with the gold expectation ST34 (gold alleles are PENDING,
  unverified values) — see docs/validation-report.md Strain-specific findings. Literature
  verification on 2026-09-07 (Sia 2020 PMC7067213): English mcr-1 Typhimurium = ST34×12 +
  **ST19×1** + ST36×6, and this strain is a biphasic serotype (consistent with ST19) — the
  evidence chain favors the pipeline being correct and the gold value being an unverified
  inference; final confirmation requires Table S1 / registered EnteroBase access.
