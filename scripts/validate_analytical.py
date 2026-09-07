"""Analytical validation harness（project.md §12.3，V0.7 Wave 3）。

Gold standard 期望值（gold_standard.jsonl）vs 管线实际输出
（results/<sid>/report/<sid>_summary.json → StrainFacts），
产出 §12.3 指标：物种/MLST/血清型准确率、AMR 灵敏度/精确度
（精确度作为特异度的基因检出 FDR 代理——真阴性空间为整个 CARD DB，
无法枚举，见报告 Caveats）。

用法：
    python scripts/validate_analytical.py [--results DIR] [--gold FILE] [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from hermes_bacmap.analysis.gene_identity import normalize_amr  # noqa: E402
from hermes_bacmap.analysis.nli_reflector import extract_facts  # noqa: E402
from hermes_bacmap.analysis.nli_types import StrainFacts  # noqa: E402

# project.md §12.3 验证指标门槛。
SPECIES_TARGET = 0.99
MLST_TARGET = 0.99
SEROTYPE_TARGET = 0.95
AMR_SENSITIVITY_TARGET = 0.95
AMR_PRECISION_TARGET = 0.98

_EXPECTED_SPECIES_CANONICAL: tuple[tuple[str, str], ...] = (
    ("salmonella", "Salmonella"),
    ("escherichia coli", "E. coli"),
    ("shigella", "Shigella"),
    ("vibrio parahaemolyticus", "V. parahaemolyticus"),
)


@dataclass(frozen=True)
class GoldExpectation:
    strain_id: str
    species_canonical: str
    serovar: str
    mlst_st: str | None
    amr_genes: tuple[str, ...]
    virulence_genes: tuple[str, ...]
    plasmid_replicons: tuple[str, ...]
    amr_list_complete: bool


@dataclass(frozen=True)
class StrainEvaluation:
    strain_id: str
    species_match: bool
    mlst_match: bool | None
    serovar_match: bool | None
    amr_tp: int
    amr_fn: int
    amr_fp: int
    amr_fn_genes: tuple[str, ...]
    amr_fp_genes: tuple[str, ...]
    plasmid_tp: int
    plasmid_expected: int
    amr_list_complete: bool


@dataclass(frozen=True)
class MetricsReport:
    n_strains: int
    n_mlst_evaluated: int
    n_serotype_evaluated: int
    n_amr_precision_strains: int
    species_accuracy: float | None
    mlst_accuracy: float | None
    serotype_accuracy: float | None
    amr_tp: int
    amr_fn: int
    amr_fp: int
    amr_sensitivity: float | None
    amr_precision: float | None
    amr_precision_tp: int
    amr_precision_fp: int
    plasmid_tp: int
    plasmid_expected: int
    meets_species_target: bool | None
    meets_mlst_target: bool | None
    meets_serotype_target: bool | None
    meets_amr_sensitivity_target: bool | None
    meets_amr_precision_target: bool | None


def _canonical_expected_species(species: str) -> str | None:
    cf = species.strip().casefold()
    for prefix, canonical in _EXPECTED_SPECIES_CANONICAL:
        if cf.startswith(prefix):
            return canonical
    return None


def load_gold_standard(path: Path) -> list[GoldExpectation]:
    """读取 gold_standard.jsonl；整体 PENDING（无物种/无 FASTQ）的 GAP 行跳过。"""
    expectations = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        canonical = _canonical_expected_species(str(row.get("species", "")))
        if canonical is None:
            continue
        mlst = row.get("mlst", {})
        st = mlst.get("st") if isinstance(mlst, dict) else None
        st_raw = str(st) if st is not None else ""
        # "PENDING"（GAP 行）与 "N/A ..."（参考株，如 K-12 MG1655）均无比较意义
        st_str = st_raw if st_raw and st_raw != "PENDING" and not st_raw.startswith("N/A") else None
        amr = row.get("amr", {})
        vir = row.get("virulence", {})
        list_complete = bool(amr.get("list_complete", False) if isinstance(amr, dict) else False)
        expectations.append(
            GoldExpectation(
                strain_id=str(row["strain_id"]),
                species_canonical=canonical,
                serovar=str(row.get("serovar", "")),
                mlst_st=st_str,
                amr_genes=tuple(amr.get("genes", []) if isinstance(amr, dict) else []),
                virulence_genes=tuple(vir.get("genes", []) if isinstance(vir, dict) else []),
                plasmid_replicons=tuple(row.get("plasmid_replicons", []) or []),
                amr_list_complete=list_complete,
            )
        )
    return expectations


def _cf_set(values: tuple[str, ...]) -> frozenset[str]:
    return frozenset(v.casefold() for v in values if v)


def evaluate_strain(exp: GoldExpectation, facts: StrainFacts) -> StrainEvaluation:
    """单株比对：物种/ST/血清型（不适用品类跳过）+ AMR/质粒集合比较。"""
    mlst_match = None
    if exp.mlst_st is not None:
        mlst_match = facts.mlst_st == exp.mlst_st

    serovar_match = None
    if facts.species == "Salmonella" and exp.serovar not in ("", "PENDING", "N/A"):
        serovar_match = facts.serotype.casefold() == exp.serovar.casefold()

    exp_amr = frozenset(normalize_amr(g) for g in exp.amr_genes)
    act_amr = frozenset(normalize_amr(g) for g in facts.amr_genes)
    tp = exp_amr & act_amr
    fn = exp_amr - act_amr
    fp = act_amr - exp_amr

    exp_pl = _cf_set(exp.plasmid_replicons)
    act_pl = _cf_set(facts.plasmids)

    raw_amr = {normalize_amr(g): g for g in (*exp.amr_genes, *facts.amr_genes)}
    return StrainEvaluation(
        strain_id=exp.strain_id,
        species_match=facts.species == exp.species_canonical,
        mlst_match=mlst_match,
        serovar_match=serovar_match,
        amr_tp=len(tp),
        amr_fn=len(fn),
        amr_fp=len(fp),
        amr_fn_genes=tuple(raw_amr[g] for g in sorted(fn)),
        amr_fp_genes=tuple(raw_amr[g] for g in sorted(fp)),
        plasmid_tp=len(exp_pl & act_pl),
        plasmid_expected=len(exp_pl),
        amr_list_complete=exp.amr_list_complete,
    )


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def _verdict(value: float | None, target: float) -> bool | None:
    return None if value is None else value >= target


def aggregate(evals: list[StrainEvaluation]) -> MetricsReport:
    n = len(evals)
    mlst_evals = [e.mlst_match for e in evals if e.mlst_match is not None]
    sero_evals = [e.serovar_match for e in evals if e.serovar_match is not None]
    tp = sum(e.amr_tp for e in evals)
    fn = sum(e.amr_fn for e in evals)
    fp = sum(e.amr_fp for e in evals)
    pl_tp = sum(e.plasmid_tp for e in evals)
    pl_exp = sum(e.plasmid_expected for e in evals)

    # Precision 仅对 amr.list_complete=true 的株计算（期望清单断言完整，
    # 如 NCBI PD 全基因型）：abricate_CARD 自产清单截断至 15 基因，其 FP
    # 源于清单不完整，进分母会系统性低估 precision。
    complete = [e for e in evals if e.amr_list_complete]
    v_tp = sum(e.amr_tp for e in complete)
    v_fp = sum(e.amr_fp for e in complete)

    species_acc = _ratio(sum(1 for e in evals if e.species_match), n)
    mlst_acc = _ratio(sum(1 for m in mlst_evals if m), len(mlst_evals))
    sero_acc = _ratio(sum(1 for s in sero_evals if s), len(sero_evals))
    sensitivity = _ratio(tp, tp + fn)
    precision = _ratio(v_tp, v_tp + v_fp)

    return MetricsReport(
        n_strains=n,
        n_mlst_evaluated=len(mlst_evals),
        n_serotype_evaluated=len(sero_evals),
        n_amr_precision_strains=len(complete),
        species_accuracy=species_acc,
        mlst_accuracy=mlst_acc,
        serotype_accuracy=sero_acc,
        amr_tp=tp,
        amr_fn=fn,
        amr_fp=fp,
        amr_sensitivity=sensitivity,
        amr_precision=precision,
        amr_precision_tp=v_tp,
        amr_precision_fp=v_fp,
        plasmid_tp=pl_tp,
        plasmid_expected=pl_exp,
        meets_species_target=_verdict(species_acc, SPECIES_TARGET),
        meets_mlst_target=_verdict(mlst_acc, MLST_TARGET),
        meets_serotype_target=_verdict(sero_acc, SEROTYPE_TARGET),
        meets_amr_sensitivity_target=_verdict(sensitivity, AMR_SENSITIVITY_TARGET),
        meets_amr_precision_target=_verdict(precision, AMR_PRECISION_TARGET),
    )


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _fmt_verdict(value: bool | None) -> str:
    return {True: "✅ PASS", False: "❌ FAIL"}.get(value, "— no data")


def _fmt_gene_list(genes: tuple[str, ...], budget: int = 170) -> str:
    """FN/FP 清单按字符预算截断（完整清单在 metrics.json 的 per_strain 里）。"""
    if not genes:
        return "—"
    parts: list[str] = []
    used = 0
    for gene in genes:
        cost = len(gene) + (2 if parts else 0)
        if used + cost > budget:
            parts.append(f"+{len(genes) - len(parts)} more")
            break
        parts.append(gene)
        used += cost
    return ", ".join(parts)


def render_markdown(report: MetricsReport, evals: list[StrainEvaluation]) -> str:
    lines = [
        "# Analytical Validation Report",
        "",
        "> Generated by `scripts/validate_analytical.py`（project.md §12.3）。",
        "",
        "## Per-strain results",
        "",
        "| strain | species | MLST ST | serovar | AMR tp/fn/fp | plasmid |",
        "|---|---|---|---|---|---|",
    ]
    for e in evals:
        lines.append(
            f"| {e.strain_id} | {'✅' if e.species_match else '❌'} "
            f"| {'✅' if e.mlst_match else '❌' if e.mlst_match is False else '—'} "
            f"| {'✅' if e.serovar_match else '❌' if e.serovar_match is False else '—'} "
            f"| {e.amr_tp}/{e.amr_fn}/{e.amr_fp} | {e.plasmid_tp}/{e.plasmid_expected} |"
        )
        if e.amr_fn_genes or e.amr_fp_genes:
            lines.append(f"  - FN: {_fmt_gene_list(e.amr_fn_genes)}")
            lines.append(f"  - FP: {_fmt_gene_list(e.amr_fp_genes)}")
    lines += [
        "",
        "## Aggregate metrics",
        "",
        f"- strains evaluated: **{report.n_strains}**"
        f"（MLST {report.n_mlst_evaluated}，serotype {report.n_serotype_evaluated}）",
        f"- species accuracy: **{_fmt_pct(report.species_accuracy)}**",
        f"- MLST ST accuracy: **{_fmt_pct(report.mlst_accuracy)}**",
        f"- serotype accuracy: **{_fmt_pct(report.serotype_accuracy)}**",
        f"- AMR sensitivity: **{_fmt_pct(report.amr_sensitivity)}**"
        f"（TP={report.amr_tp} FN={report.amr_fn}）",
        f"- AMR precision: **{_fmt_pct(report.amr_precision)}**"
        f"（断言完整清单株 {report.n_amr_precision_strains} 个，"
        f"TP={report.amr_precision_tp} FP={report.amr_precision_fp}，与 percentage 同口径；"
        f"全株合并 TP={report.amr_tp} FP={report.amr_fp} 为信息性计数）",
        f"- plasmid recall: {_fmt_pct(_ratio(report.plasmid_tp, report.plasmid_expected))}",
        "",
        "## §12.3 target verdicts",
        "",
        "| metric | actual | target | verdict |",
        "|---|---|---|---|",
        f"| species accuracy | {_fmt_pct(report.species_accuracy)} | ≥99% "
        f"| {_fmt_verdict(report.meets_species_target)} |",
        f"| MLST ST accuracy | {_fmt_pct(report.mlst_accuracy)} | ≥99% "
        f"| {_fmt_verdict(report.meets_mlst_target)} |",
        f"| serotype accuracy | {_fmt_pct(report.serotype_accuracy)} | ≥95% "
        f"| {_fmt_verdict(report.meets_serotype_target)} |",
        f"| AMR sensitivity | {_fmt_pct(report.amr_sensitivity)} | ≥95% "
        f"| {_fmt_verdict(report.meets_amr_sensitivity_target)} |",
        f"| AMR precision (specificity proxy) | {_fmt_pct(report.amr_precision)} | ≥98% "
        f"| {_fmt_verdict(report.meets_amr_precision_target)} |",
        "",
        "## Caveats",
        "",
        "- AMR precision 是基因检出 FDR 的代理指标：真阴性空间为整个 CARD DB，",
        "  无法枚举（project.md §12.3 的 specificity 在基因面板受限场景取 precision）。",
        "- 多数 gold standard 行的 amr_genes 证据来源即 abricate_CARD（管线自产），",
        "  此类行衡量的是重跑一致性 + DB 漂移，而非独立方法学验证；",
        "  NCBI/ENA 独立验证的行为 CTX-008（blaCTX-M-15）与 MCR-010（mcr-1）。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=_ROOT / "results")
    parser.add_argument(
        "--gold",
        type=Path,
        default=_ROOT / "tests/fixtures/gold_standard/salmonella/gold_standard.jsonl",
    )
    parser.add_argument("--out-dir", type=Path, default=_ROOT / "results/validation")
    args = parser.parse_args()

    expectations = load_gold_standard(args.gold)
    evals: list[StrainEvaluation] = []
    skipped: list[str] = []
    for exp in expectations:
        summary = args.results / exp.strain_id / "report" / f"{exp.strain_id}_summary.json"
        if not summary.exists():
            skipped.append(exp.strain_id)
            continue
        with summary.open() as f:
            facts = extract_facts(json.load(f), exp.strain_id)
        evals.append(evaluate_strain(exp, facts))

    if not evals:
        print("no evaluable strains (missing results?)", file=sys.stderr)
        return 1

    report = aggregate(evals)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "metrics.json").write_text(
        json.dumps(
            {
                **{k: getattr(report, k) for k in report.__dataclass_fields__},
                "per_strain": [{k: getattr(e, k) for k in e.__dataclass_fields__} for e in evals],
                "skipped_no_results": skipped,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    md = render_markdown(report, evals)
    (args.out_dir / "validation-report.md").write_text(md)
    print(md)
    print(f"\nmetrics: {args.out_dir / 'metrics.json'}")
    print(f"report : {args.out_dir / 'validation-report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
