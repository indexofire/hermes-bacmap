# Code Quality Assessment and Remediation Roadmap

> Assessment date: 2026-07-18 · Baseline: V0.5.0 (commit `844d058`) · Method: full code read-through + hands-on quality tools (ruff / mypy --strict / pytest --cov)

## 1. Overall Conclusion

The project's architectural design awareness is above average: clean layering, a carefully modeled GOM persistence layer
(immutable objects + version chains + event sourcing), and good test coverage of the services layer. However, at assessment
time **every quality gate had effectively failed** — lint failing, mypy crashing at startup, the 80% coverage gate actually
at 28%, CI configuration contradicting `requires-python`, plus a broken code branch that had never been executed.

After three phases of concentrated remediation, all quality gates are now genuinely green, and 8 groups of real bugs were
fixed along the way (including 2 high-severity bugs affecting the correctness of analysis conclusions).

**Scores (at assessment) → (after remediation)**

| Dimension | At assessment | After remediation |
|---|---|---|
| Architecture | 7.5/10 | 8.5/10 (phase 3 structural refactoring complete: god-module split, circular dependencies broken, shared layer extracted) |
| Code quality | 5/10 | 9/10 (all gates green, coverage 92.21%) |

## 2. Architecture Assessment

### Layered structure

```
tools/              LLM facade layer (24 tool handlers, packaged by seq/cli/pipeline/services, JSON in/out)
    ↓ lazy loading
analysis/           algorithm layer (gene_scanner, species_identifier, verifier…)
    ↓
engine/             CLI abstraction layer (SequenceMatcher/ReadMapper + backend registry)
    ↓
backends/           blast / minimap2 / kma / mash / sourmash
services/           persistence layer (GOM + strain_index + metadata + lab_results + sample_summary, dependency-free)
```

### Architectural strengths

- `engine/` abstraction layer: `Registry` lazy-loads backends, `SequenceMatcher` auto-selects the backend by query size (>10MB → minimap2), decoupling pipeline logic from specific CLI tools.
- `services/genome_object_service.py`: frozen dataclass enforcing immutability, semver validation, evidence chain
  (pipeline_version + database_versions) enforced in `__post_init__`, SQLite WAL + FTS5; design cross-referenced
  and traceable against project.md §4/§5.
- The tool-handler convention of "never raise, convert errors to JSON" is the right design for LLM scenarios.
- Reference database paths centralized in the `db.py` registry; `config.py` supports environment-variable overrides.

### Architectural issues (all resolved, 2026-07-18)

| Issue | Location | Status |
|---|---|---|
| 1887-line god module, 24 handlers in one file | `tools.py` | ✅ Split into the `tools/` package (seq / cli / pipeline / services + `_common` + `registry`), with `@tool_handler` as the unified error backstop |
| 1012-line engine class with nested closures, hard to unit test | `typing/vpa_serotyper_engine.py` | ✅ Split into `_vpa_kmer` / `_vpa_genes` / `_vpa_report` + a 430-line orchestration facade; 6 closures converted to pure functions; 6 whole-DB scans converged into a `_RefFasta` cache |
| Soft circular dependency (mutual lazy imports) | `species_identifier ↔ taxonomic_validator` | ✅ Cycle broken: removed the `identify(mode="standard")` pass-through branch; dependency now one-way |
| Sub-package `__init__.py` all empty, no `__all__` | `analysis/ services/ typing/` | ✅ Exports + `__all__` added |
| Sample-status logic duplicated in two places | `scripts/run_analysis.py`, `web/app.py` | ✅ Extracted into the shared `services/sample_summary.py` layer |
| 24 repeated registration blocks | `__init__.py:register()` | ✅ Replaced by a single `tools/registry.py` table + a for loop (28 lines) |

## 3. Measured Data at Assessment (pre-remediation baseline, 2026-07-18)

| Gate | Configuration | Measured | Verdict |
|---|---|---|---|
| ruff check + format | all green | 29 errors + 24 unformatted files | ❌ |
| mypy --strict | 0 errors | Crashed at startup (missing mappy/sourmash stubs + Python version mismatch), **never actually analyzed business code**; fixing startup exposed 203 errors | ❌ |
| pytest coverage | `fail_under = 80` | **28.35%** | ❌ |
| CI python-version | 3.12 (requires-python) | All jobs used 3.11, `pip install -e .` was guaranteed to fail | ❌ |

Coverage chasm (before remediation): services 83–93% vs `tools.py` 4%, all of `typing/` 0%, `engine/backends/` 0%.

## 4. Remediation Log

### Phase 0 — Gate restoration (2026-07-18)

1. Unified Python version to 3.12 (pyproject ruff/mypy targets, ci.yml × 5, test_env.py assertions).
2. mypy overrides for `mappy`/`sourmash`; fixed all 203 type errors (real annotations; only 9 targeted `type: ignore` comments remain with specific error codes, all for stub-less Biopython calls).
3. Full repair via `ruff check --fix` + `ruff format`.
4. Merged duplicate same-named test classes in `test_engine.py` (one class's tests had been silently swallowed).
5. Generated `.secrets.baseline` (excludes high-entropy false positives from `data/` biological sequences); pre-commit detect-secrets restored to working order.
6. Removed 22 lines of unreachable dead code after `return` in `engine/backends/kmer.py`.

### Phase 1 — Confirmed bug fixes + duplication convergence (2026-07-18)

- **Fixed 3 guaranteed-crash points in the `_scan_reads` FASTQ branch** (`gene_scanner.py`): `ScanResult(query=…)` field
  does not exist, `GeneHit(evalue=/depth=)` fields do not exist, `result.all_hits` attribute does not exist —
  this branch had never been runnable.
- Fixed cross-module private import of `_PROJECT_ROOT` in `typing/vpa_serotyper.py` → now formally imported from `config`.
- **7 MLST parsers → single `utils.parse_mlst` implementation** (deterministic_verifier, tools.get_result,
  tools.search_samples, strain_index, web/app.py, run_analysis.py); the original web/app.py and run_analysis.py
  implementations read the wrong column (returning the last allele instead of the ST), fixed as part of the convergence.
- Converged duplicate `which`/`pixi_path` definitions: `engine/_env.py` now re-exports from `config.py`, zero caller changes.
- 21 bare `except Exception` in `tools.py` got `logger.exception` (17 added + 4 existing); exceptions are no longer silently swallowed.

### Phase 2 — Coverage brought up to standard (2026-07-18)

Added ~750 unit tests (4 parallel workstreams along module boundaries): parser classes use static sample text,
all CLI boundaries mocked (tests run without binaries installed), handler classes mock subprocess + real
services layer on tmp SQLite.

| Module | Before | After |
|---|---|---|
| `tools.py` | 4% | 92% |
| `engine/` (overall) | 0–39% | 92–100% |
| `analysis/` (overall) | 15–56% | 90–100% |
| `typing/` (except vpa_engine) | 0% | 83–100% |
| `typing/vpa_serotyper_engine.py` | 0% | 49% |
| `db.py` / `schemas.py` | 0% / 100% | 100% / 100% |
| **Total** | **28.35%** | **86.07% → 90.26%** (after bug fixes) |

### 5 groups of production bugs found by test-driven development (all fixed)

| # | Location | Problem and fix |
|---|---|---|
| 1 🔴 | `analysis/species_identifier.py` | `identify()` lowercased keys but probed with mixed case, so **Salmonella/DEC/Shigella/toxR identification never fired**. Fix: removed the duplicated if-chain, now looks up the `_SPECIES_PRIORITY` + `_GENE_TO_SPECIES` tables (single source of truth). |
| 2 🔴 | `typing/shigella_serotyper.py` | `_FLEXNERI_RULES` short-circuits in order; medium subset rules matched before exact rules, **misclassifying 11+ serotypes** (1b/1c/2b/2av/4av/5b/7b/Xv/3a/4b/4bv). Fix: two-pass scheme — full exact match first (high), then nearest match if none (medium, more specific rules first). |
| 3 🟡 | `analysis/failure_diagnostics.py` | Regexes `\\.nhr`/`\\.phr`/`\\.pixi` required literal backslashes. Fix: changed to `\.`. |
| 4 🟡 | `analysis/failure_diagnostics.py` | Unknown-error exit codes were overwritten by the "last 3 lines" fallback. Fix: changed to append. |
| 5 🟢 | `tools.py:seq_convert` | `_resolve_path('')` returned CWD, defeating output_file validation. Fix: empty-check before resolve. |

## 5. Current Quality Gate Status (2026-07-18, after structural refactoring)

```
ruff check src/ tests/        ✅ All checks passed
ruff format --check           ✅ 80 files already formatted
mypy --strict src/            ✅ Success: no issues found in 44 source files
pytest tests/                 ✅ 1051 passed
coverage (branch, fail_under=80) ✅ 92.41%
```

## 6. Remaining Items (phase 3 roadmap)

Ordered by recommended priority:

1. ~~**Commit and protect the results**~~ ✅ (done 2026-07-18): split into 4 atomic commits — `12cd7e9` config gates, `d5a4525` bug fixes + convergence, `a828d7e` test expansion, `be2c59b` assessment docs.
2. ~~**Minor duplication convergence**~~ ✅ (done 2026-07-18): the `~~~` header parsing in `kma._parse_template` and
   `gene_scanner._parse_db_header` merged into a single `utils.parse_db_header`, with thin delegates kept at both call sites.
3. ~~**Documentation reconciliation**~~ ✅ (done 2026-07-18): tool count unified to 24 (7 conflicting mentions of 17/19/23),
   test count 193 → 994, README/overview/features module line-count tables updated from measurements,
   rule count unified to 24 (10 .smk files with 23 rules + Snakefile `rule all`), 7 dead links fixed,
   `tools.md`/`features.md` gained the 5–7 previously missing tools.
4. ~~**sourmash deprecated-API migration**~~ ✅ (done 2026-07-18): `load_signatures` → `load_file_as_signatures`,
   `save_signatures` → `SaveSignaturesToLocation`; all 45 deprecation warnings eliminated
   (only 1 third-party fastapi warning remains in the suite).
5. ~~**Structural refactoring**~~ ✅ (done 2026-07-18): `tools.py` split into the `tools/` package
   (seq / cli / pipeline / services + `_common` shared base + `@tool_handler` unified error backstop,
   plus protection added to 5 unprotected handlers) + table-driven `tools/registry.py` registration;
   `vpa_serotyper_engine.py` split by kmer ranking / gene verification / report generation into
   `_vpa_kmer` / `_vpa_genes` / `_vpa_report` (6 closures converted to pure functions,
   6 whole-DB scans converged into a `_RefFasta` cache, dead attributes removed),
   the engine slimmed to a 430-line orchestration facade keeping private-method delegates for test compatibility;
   sample-status logic extracted into `services/sample_summary.py` shared by scripts and web;
   the `species_identifier → taxonomic_validator` circular dependency broken;
   sub-packages gained `__init__.py` exports + `__all__`. `schemas.py` kept as a single file (pure data, no benefit from splitting).
6. ~~**Integration tests**~~ ✅ (done 2026-07-18): `web/app.py` gained 13 FastAPI TestClient smoke tests
   (status/detail/annotation/SNP/search/metadata/lab-results routes);
   added 5 end-to-end tests in `test_vpa_e2e.py` (real RIMD 2210633 genome → O3:K6 Perfect,
   Salmonella/E. coli negative controls); CI gained a `snakemake-dag` job and installs the web extra
   so smoke tests enter the pipeline.
