"""生成 HTML 分析报告（project.md §7.3 report step）。

用法:
    python scripts/generate_report.py --sample SAM-TYP-001
    python scripts/generate_report.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from _common import ROOT

sys.path.insert(0, str(ROOT / "src"))

from hermes_bacmap.analysis.deterministic_verifier import DeterministicVerifier
from hermes_bacmap.utils import parse_abricate_tsv, parse_mlst

RESULTS_DIR = ROOT / "results"


def _row(label: str, value: str, ok: bool = True) -> str:
    cls = "ok" if ok else "fail"
    return f'<tr><td class="label">{label}</td><td class="{cls}">{value}</td></tr>'


def _gene_table(genes: list[dict], title: str) -> str:
    if not genes:
        return f"<h3>{title}</h3><p>未检出</p>"
    rows = "".join(
        f"<tr><td>{g.get('GENE','?')}</td><td>{g.get('%IDENTITY','?')}</td>"
        f"<td>{g.get('%COVERAGE','?')}</td><td>{g.get('RESISTANCE','')}</td></tr>"
        for g in genes[:20]
    )
    extra = f"<p><em>显示前 20 个，共 {len(genes)} 个</em></p>" if len(genes) > 20 else ""
    return f"""
    <h3>{title} ({len(genes)} genes)</h3>
    <table><tr><th>Gene</th><th>%Identity</th><th>%Coverage</th><th>Resistance</th></tr>
    {rows}</table>{extra}"""


def generate_html(sample_id: str, summary: dict, verification, output_path: Path):
    steps = summary.get("steps", {})

    sp = steps.get("species", {})
    verdict = sp.get("verdict", "N/A") if isinstance(sp, dict) else str(sp)

    mlst_info = parse_mlst(steps.get("mlst", ""))
    st = mlst_info.get("st", "N/A")
    alleles = mlst_info.get("alleles", {})

    sero = steps.get("serotype", {})
    serovar = sero.get("sistr", "N/A") if isinstance(sero, dict) else "N/A"
    serogroup = sero.get("serogroup", "") if isinstance(sero, dict) else ""
    o_antigen = sero.get("o_antigen", "") if isinstance(sero, dict) else ""
    h1 = sero.get("h1", "") if isinstance(sero, dict) else ""
    h2 = sero.get("h2", "") if isinstance(sero, dict) else ""

    card_genes = parse_abricate_tsv("")
    card_path = RESULTS_DIR / sample_id / "amr" / "abricate_card.tsv"
    if card_path.exists():
        card_genes = parse_abricate_tsv(card_path.read_text())
    vfdb_path = RESULTS_DIR / sample_id / "amr" / "abricate_vfdb.tsv"
    vfdb_genes = parse_abricate_tsv(vfdb_path.read_text()) if vfdb_path.exists() else []
    plasmid_path = RESULTS_DIR / sample_id / "plasmid" / "abricate_plasmidfinder.tsv"
    plasmid_genes = parse_abricate_tsv(plasmid_path.read_text()) if plasmid_path.exists() else []

    asm_stats = steps.get("assembly", "")
    asm_parts = asm_stats.strip().split("\n")[-1].split("\t") if asm_stats else []
    num_contigs = asm_parts[2] if len(asm_parts) > 2 else "?"
    total_len = asm_parts[4] if len(asm_parts) > 4 else "?"

    v_icon = "✅" if verification.passed else "❌"
    v_review = '<span class="warn">⚠️ 需要人工审核</span>' if verification.needs_human_review else ""

    check_rows = "".join(
        f'<tr><td>{c.name}</td><td class="{"ok" if c.passed else "fail"}">'
        f'{"✅" if c.passed else "❌"} {c.message}</td></tr>'
        for c in verification.checks
    )

    allele_str = " ".join(f"{k}={v}" for k, v in alleles.items()) if alleles else "N/A"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{sample_id} 分析报告</title>
<style>
body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; color: #333; }}
h1 {{ color: #1a5276; border-bottom: 3px solid #2980b9; padding-bottom: 0.3em; }}
h2 {{ color: #2874a6; margin-top: 1.5em; }}
h3 {{ color: #2e86c1; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.5em 0; }}
th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 0.9em; }}
th {{ background: #ebf5fb; }}
td.label {{ font-weight: bold; width: 180px; background: #f8f9fa; }}
.ok {{ color: #27ae60; }}
.fail {{ color: #e74c3c; }}
.warn {{ color: #f39c12; font-weight: bold; }}
.verdict-box {{ display: inline-block; padding: 8px 20px; border-radius: 6px; font-size: 1.2em; font-weight: bold; margin: 10px 0; }}
.verdict-pass {{ background: #d4edda; color: #155724; }}
.verdict-fail {{ background: #f8d7da; color: #721c24; }}
.evidence {{ background: #f0f0f0; padding: 10px; border-radius: 5px; font-size: 0.85em; margin-top: 2em; }}
</style></head>
<body>
<h1>🧬 {sample_id} 全基因组分析报告</h1>
<p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

<div class="verdict-box {"verdict-pass" if verification.passed else "verdict-fail"}">
{v_icon} Verifier: {"ALL PASSED" if verification.passed else f"{verification.failed_count} FAILED"} {v_review}
</div>

<h2>📋 基本信息</h2>
<table>
{_row("样本编号", sample_id)}
{_row("物种判定", verdict, "Salmonella" in verdict)}
{_row("MLST ST", st)}
{_row("MLST Alleles", allele_str)}
{_row("血清型", serovar)}
{_row("血清群", serogroup)}
{_row("抗原式", f"{o_antigen}:{h1}:{h2}")}
{_row("Contigs 数", num_contigs)}
{_row("组装总长度", f"{total_len} bp")}
</table>

<h2>🔬 Deterministic Verifier 校验</h2>
<table>
<tr><th>检查项</th><th>结果</th></tr>
{check_rows}
</table>

<h2>💊 AMR 耐药基因 (CARD)</h2>
{_gene_table(card_genes, "CARD AMR Genes")}

<h2>🦠 毒力基因 (VFDB)</h2>
{_gene_table(vfdb_genes, "VFDB Virulence Genes")}

<h2>🧬 质粒复制子 (PlasmidFinder)</h2>
{_gene_table(plasmid_genes, "PlasmidFinder")}

<div class="evidence">
<h3>📌 三元证据链 (project.md §4.5)</h3>
<p><strong>strain_id:</strong> {sample_id}</p>
<p><strong>pipeline_version:</strong> {summary.get("pipeline_version", "salmonella-workflow-v0.1")}</p>
<p><strong>tool_versions:</strong> fastp, Shovill 1.1.0, blastn 2.17.0+, gmlst 0.1.0, SISTR 1.1.3, abricate 1.4.0</p>
<p><strong>database_versions:</strong> CARD 2026-Apr-3, VFDB 2026-Apr-3, PlasmidFinder 2026-Apr-3, PubMLST salmonella_2</p>
</div>

</body></html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def _distance_color(d: int, max_d: int) -> str:
    if max_d == 0:
        return "#ffffff"
    ratio = d / max_d
    r = int(255 * ratio)
    g = int(255 * (1 - ratio))
    return f"rgb({r},{g},80)"


def generate_cohort_html(snp_summary: dict, output_path: Path):

    newick = snp_summary.get("tree_newick", "")
    n_sites = snp_summary.get("n_snp_sites", 0)
    n_samples = snp_summary.get("n_samples", 0)
    missing = snp_summary.get("missing_rate", 0)
    samples = snp_summary.get("samples", [])
    distances = snp_summary.get("pairwise_distances", {})

    max_d = max(distances.values()) if distances else 1

    dist_header = "".join(f"<th>{s}</th>" for s in samples)
    dist_rows = ""
    for i, s1 in enumerate(samples):
        cells = f"<td class='label'>{s1}</td>"
        for j, s2 in enumerate(samples):
            if i == j:
                cells += "<td style='text-align:center;color:#aaa;'>—</td>"
            elif i < j:
                key = f"{s1}|{s2}"
                d = distances.get(key, 0)
                color = _distance_color(d, max_d)
                cells += f"<td style='background:{color};text-align:right;'>{d}</td>"
            else:
                key = f"{s2}|{s1}"
                d = distances.get(key, 0)
                color = _distance_color(d, max_d)
                cells += f"<td style='background:{color};text-align:right;opacity:0.5;'>{d}</td>"
        dist_rows += f"<tr>{cells}</tr>\n"

    newick_escaped = newick.replace("\\", "\\\\").replace("'", "\\'")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>SNP 系统发育分析报告</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="https://raw.githack.com/rdvelin/phylotree.js/master/dist/phylotree.js"></script>
<link rel="stylesheet" href="https://raw.githack.com/rdvelin/phylotree.js/master/dist/phylotree.css">
<style>
body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #333; }}
h1 {{ color: #1a5276; border-bottom: 3px solid #2980b9; padding-bottom: 0.3em; }}
h2 {{ color: #2874a6; margin-top: 1.5em; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.5em 0; font-size: 0.85em; }}
th, td {{ border: 1px solid #ddd; padding: 4px 8px; text-align: left; }}
th {{ background: #ebf5fb; }}
td.label {{ font-weight: bold; background: #f8f9fa; }}
.stats-box {{ display: flex; gap: 20px; margin: 1em 0; }}
.stat-card {{ background: #ebf5fb; padding: 12px 24px; border-radius: 8px; text-align: center; }}
.stat-card .value {{ font-size: 1.8em; font-weight: bold; color: #2980b9; }}
.stat-card .label {{ font-size: 0.85em; color: #666; }}
#tree-container {{ background: #fff; border: 1px solid #ddd; border-radius: 5px; padding: 10px; min-height: 400px; }}
.fallback-tree {{ font-family: monospace; white-space: pre; font-size: 0.8em; background: #f8f9fa; padding: 1em; overflow-x: auto; }}
</style></head>
<body>
<h1>🌲 SNP 系统发育分析报告</h1>
<p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

<div class="stats-box">
<div class="stat-card"><div class="value">{n_samples}</div><div class="label">样本数</div></div>
<div class="stat-card"><div class="value">{n_sites:,}</div><div class="label">SNP 位点数</div></div>
<div class="stat-card"><div class="value">{missing*100:.1f}%</div><div class="label">缺失率</div></div>
<div class="stat-card"><div class="value">{len(distances)}</div><div class="label">比较对数</div></div>
</div>

<h2>🌳 系统发育树 (Maximum Likelihood, GTR+UFBoot1000)</h2>
<div id="tree-container"></div>
<div class="fallback-tree" id="fallback">{newick}</div>

<h2>📊 SNP 距离矩阵</h2>
<table>
<tr><th>样本</th>{dist_header}</tr>
{dist_rows}
</table>

<script>
if (typeof d3 !== 'undefined' && typeof phylotree !== 'undefined') {{
    var tree = d3.layout.phylotree()
        .svg(d3.select("#tree-container").append("svg:svg"))
        .options({{'selectable': false, 'collapsible': false}});
    tree({newick_escaped});
    tree.layout();
    document.getElementById('fallback').style.display = 'none';
}}
</script>

</body></html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 HTML 分析报告")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", type=str)
    group.add_argument("--all", action="store_true")
    group.add_argument("--cohort", action="store_true")
    args = parser.parse_args()

    if args.cohort:
        snp_path = RESULTS_DIR / "snp" / "snp_summary.json"
        if not snp_path.exists():
            print(f"  ✗ {snp_path} not found. Run snp_summary rule first.")
            return 1
        snp_summary = json.loads(snp_path.read_text())
        output = RESULTS_DIR / "snp" / "cohort_report.html"
        generate_cohort_html(snp_summary, output)
        print(f"  ✅ Cohort report: {output}")
        return 0

    v = DeterministicVerifier()

    if args.all:
        import csv
        with (ROOT / "workflows/salmonella/config/samples.tsv").open() as f:
            samples = [r["sample"] for r in csv.DictReader(f, delimiter="\t")]
    else:
        samples = [args.sample]

    for sid in samples:
        sp = RESULTS_DIR / sid / "report" / f"{sid}_summary.json"
        if not sp.exists():
            print(f"  ✗ {sid}: summary.json not found")
            continue
        with sp.open() as f:
            summary = json.load(f)
        verification = v.verify_all(summary)
        output = RESULTS_DIR / sid / "report" / f"{sid}_report.html"
        generate_html(sid, summary, verification, output)
        icon = "✅" if verification.passed else "⚠️"
        print(f"  {icon} {sid}: {output.name} ({'passed' if verification.passed else 'NEEDS REVIEW'})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
