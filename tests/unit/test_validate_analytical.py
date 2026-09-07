"""TDD 测试：scripts/validate_analytical.py（V0.7 Wave 3，project.md §12.3）。

分析验证 harness：gold_standard.jsonl 期望值 vs 管线实际输出（summary.json
→ StrainFacts），产出 §12.3 指标（物种/MLST/血清型准确率、AMR 灵敏度/精
确度）与 per-strain 明细。纯函数测试，不跑管线、不联网。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
_SRC_DIR = _PROJECT_ROOT / "src"

for _p in (_SCRIPTS_DIR, _SRC_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_SPEC = importlib.util.spec_from_file_location(
    "validate_analytical", _SCRIPTS_DIR / "validate_analytical.py"
)
assert _SPEC is not None and _SPEC.loader is not None
validate_analytical = importlib.util.module_from_spec(_SPEC)
# Python 3.12: @dataclass 解析 __module__ 时要求模块已注册（否则
# sys.modules.get(...).__dict__ 抛 NoneType）。
sys.modules["validate_analytical"] = validate_analytical
_SPEC.loader.exec_module(validate_analytical)

evaluate = validate_analytical.evaluate_strain
aggregate = validate_analytical.aggregate
render_markdown = validate_analytical.render_markdown

from hermes_bacmap.analysis.nli_types import StrainFacts  # noqa: E402


def _exp(
    strain_id: str,
    species: str = "Salmonella enterica",
    serovar: str = "Typhimurium",
    st: int | str | None = 19,
    amr_genes: list[str] | None = None,
    plasmids: list[str] | None = None,
    amr_list_complete: bool = False,
) -> dict:
    return {
        "strain_id": strain_id,
        "species": species,
        "serovar": serovar,
        "mlst": {"scheme": "salmonella_2", "st": st, "alleles": {}},
        "amr": {
            "genes": amr_genes if amr_genes is not None else ["blaCTX-M-15"],
            "list_complete": amr_list_complete,
        },
        "virulence": {"genes": []},
        "plasmid_replicons": plasmids if plasmids is not None else ["IncFIB"],
    }


def _gold(tmp_path: Path, row: dict):
    """dict 期望行 → 经真实 loader 转成 GoldExpectation。"""
    path = tmp_path / "gold.jsonl"
    path.write_text(json.dumps(row))
    (exp,) = validate_analytical.load_gold_standard(path)
    return exp


def _facts(
    sample_id: str,
    species: str = "Salmonella",
    mlst_st: str = "19",
    serotype: str = "Typhimurium",
    amr_genes: tuple[str, ...] = ("blaCTX-M-15",),
    plasmids: tuple[str, ...] = ("IncFIB",),
) -> StrainFacts:
    return StrainFacts(
        sample_id=sample_id,
        species=species,
        mlst_st=mlst_st,
        serotype=serotype,
        amr_genes=amr_genes,
        virulence_genes=(),
        plasmids=plasmids,
    )


# ===========================================================================
# load_gold_standard
# ===========================================================================


class TestLoadGoldStandard:
    def test_loads_and_skips_pending(self, tmp_path: Path):
        rows = [
            _exp("SAM-A"),
            {"strain_id": "SAM-GAP", "species": "PENDING", "mlst": {"st": "PENDING"}},
            _exp("SAM-B", st="PENDING"),
        ]
        path = tmp_path / "gold.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows))
        loaded = validate_analytical.load_gold_standard(path)
        # 完全 PENDING 的株被跳过；st=PENDING 的株保留（字段级跳过）
        assert [e.strain_id for e in loaded] == ["SAM-A", "SAM-B"]

    def test_expected_species_canonicalized(self, tmp_path: Path):
        path = tmp_path / "gold.jsonl"
        path.write_text(json.dumps(_exp("SAM-ECO", species="Escherichia coli")))
        (e,) = validate_analytical.load_gold_standard(path)
        assert e.species_canonical == "E. coli"


# ===========================================================================
# evaluate_strain
# ===========================================================================


class TestEvaluateStrain:
    def test_full_match(self, tmp_path):
        ev = evaluate(_gold(tmp_path, _exp("SAM-A")), _facts("SAM-A"))
        assert ev.species_match is True
        assert ev.mlst_match is True
        assert ev.serovar_match is True
        assert ev.amr_tp == 1 and ev.amr_fn == 0 and ev.amr_fp == 0

    def test_species_mismatch(self, tmp_path):
        ev = evaluate(
            _gold(tmp_path, _exp("SAM-ECO", species="Escherichia coli")),
            _facts("SAM-ECO", species="Salmonella"),
        )
        assert ev.species_match is False

    def test_mlst_pending_skipped(self, tmp_path):
        ev = evaluate(_gold(tmp_path, _exp("SAM-A", st="PENDING")), _facts("SAM-A"))
        assert ev.mlst_match is None

    def test_mlst_na_reference_strain_skipped(self, tmp_path):
        """ECO-011 类参考株期望 ST 为 'N/A (K-12 reference)'——无比较意义。"""
        ev = evaluate(
            _gold(tmp_path, _exp("SAM-ECO", st="N/A (K-12 reference)")),
            _facts("SAM-ECO", mlst_st="10"),
        )
        assert ev.mlst_match is None

    def test_serovar_skipped_for_non_salmonella(self, tmp_path):
        ev = evaluate(
            _gold(
                tmp_path,
                _exp("SAM-ECO", species="Escherichia coli", serovar="K-12 MG1655"),
            ),
            _facts("SAM-ECO", species="E. coli", serotype="O16:H48"),
        )
        assert ev.serovar_match is None

    def test_amr_casefold_set_comparison(self, tmp_path):
        exp = _gold(tmp_path, _exp("SAM-A", amr_genes=["blaCTX-M-15", "tet(A)", "mcr-1"]))
        facts = _facts("SAM-A", amr_genes=("blactx-m-15", "Tet(A)", "qnrS1"))
        ev = evaluate(exp, facts)
        assert ev.amr_tp == 2
        assert ev.amr_fn == 1  # mcr-1 漏检
        assert ev.amr_fp == 1  # qnrS1 多检

    def test_negative_control_fp(self, tmp_path):
        exp = _gold(tmp_path, _exp("SAM-NEG", species="Escherichia coli", amr_genes=[]))
        facts = _facts("SAM-NEG", species="E. coli", amr_genes=("blaCTX-M-15",))
        ev = evaluate(exp, facts)
        assert ev.amr_fn == 0
        assert ev.amr_fp == 1

    def test_plasmid_recall(self, tmp_path):
        exp = _gold(tmp_path, _exp("SAM-A", plasmids=["IncFIB", "IncX1"]))
        ev = evaluate(exp, _facts("SAM-A", plasmids=("IncFIB",)))
        assert ev.plasmid_tp == 1
        assert ev.plasmid_expected == 2


# ===========================================================================
# aggregate + render
# ===========================================================================


class TestAggregate:
    def test_pooled_metrics_and_targets(self, tmp_path):
        # A 清单断言完整（进 precision 分母）；B 部分清单（recall-only）
        evals = [
            evaluate(
                _gold(
                    tmp_path,
                    _exp(
                        "SAM-A",
                        amr_genes=["blaCTX-M-15", "tet(A)"],
                        amr_list_complete=True,
                    ),
                ),
                _facts("SAM-A", amr_genes=("blaCTX-M-15", "tet(A)")),
            ),
            evaluate(
                _gold(tmp_path, _exp("SAM-B", amr_genes=["tet(A)"])),
                _facts("SAM-B", serotype="Enteritidis", amr_genes=("qnrS1",)),
            ),
        ]
        report = aggregate(evals)
        assert report.n_strains == 2
        assert report.species_accuracy == 1.0
        assert report.mlst_accuracy == 1.0
        assert report.serotype_accuracy == 0.5
        # sensitivity pooled: A tp=2 fn=0; B exp{tetA} vs act{qnrS1} tp=0 fn=1
        assert report.amr_tp == 2
        assert report.amr_fn == 1
        assert report.amr_sensitivity == pytest.approx(2 / 3)
        # precision 仅 A（list_complete）：tp=2 fp=0 → 1.0；B 的 fp 不进分母
        assert report.n_amr_precision_strains == 1
        assert report.amr_precision == 1.0

    def test_precision_none_when_no_complete_list(self, tmp_path):
        evals = [evaluate(_gold(tmp_path, _exp("SAM-A")), _facts("SAM-A"))]
        report = aggregate(evals)
        assert report.amr_precision is None
        assert report.meets_amr_precision_target is None

    def test_precision_renders_subset_counts(self, tmp_path):
        """评审 A4：precision 行显示子集 TP/FP（与 percentage 同口径）。"""
        evals = [
            evaluate(
                _gold(
                    tmp_path,
                    _exp("SAM-A", amr_genes=["tet(A)"], amr_list_complete=True),
                ),
                _facts("SAM-A", amr_genes=("tet(A)", "sul1")),
            ),
            evaluate(
                _gold(tmp_path, _exp("SAM-B", amr_genes=["tet(A)", "qnrS1"])),
                _facts("SAM-B", amr_genes=("tet(A)", "sul1", "qacE")),
            ),
        ]
        report = aggregate(evals)
        assert report.amr_tp == 2 and report.amr_fp == 3  # 合并（信息性）
        assert report.amr_precision_tp == 1 and report.amr_precision_fp == 1  # 子集
        assert report.amr_precision == pytest.approx(0.5)
        md = render_markdown(report, evals)
        assert "TP=1 FP=1" in md  # precision 行显示子集值
        assert "TP=2 FN=1" in md  # sensitivity 行保留合并值

    def test_bla_prefix_normalization(self, tmp_path):
        exp = _gold(tmp_path, _exp("SAM-A", amr_genes=["blaCTX-M-15"]))
        facts = _facts("SAM-A", amr_genes=("CTX-M-15",))
        ev = evaluate(exp, facts)
        assert ev.amr_tp == 1
        assert ev.amr_fn == 0 and ev.amr_fp == 0

    def test_mcr_variant_normalization(self, tmp_path):
        """CARD 报等位变异名 MCR-1.1，gold 用家族名 mcr-1——同一基因。"""
        exp = _gold(tmp_path, _exp("SAM-A", amr_genes=["mcr-1"]))
        facts = _facts("SAM-A", amr_genes=("MCR-1.1", "mcr-3.2", "mcr-1"))
        ev = evaluate(exp, facts)
        assert ev.amr_tp == 1
        assert ev.amr_fn == 0
        # mcr-3.2 不归一到 mcr-1（不同家族），仍是 FP
        assert ev.amr_fp == 1

    def test_target_verdicts(self, tmp_path):
        evals = [
            evaluate(
                _gold(
                    tmp_path,
                    _exp("SAM-A", amr_list_complete=True),
                ),
                _facts("SAM-A"),
            )
        ]
        report = aggregate(evals)
        assert report.meets_species_target is True
        assert report.meets_mlst_target is True
        assert report.meets_serotype_target is True
        assert report.meets_amr_sensitivity_target is True
        assert report.meets_amr_precision_target is True

    def test_render_markdown_contains_sections(self, tmp_path):
        evals = [evaluate(_gold(tmp_path, _exp("SAM-A")), _facts("SAM-A"))]
        report = aggregate(evals)
        md = render_markdown(report, evals)
        assert "## Per-strain results" in md
        assert "SAM-A" in md
        assert "## Aggregate metrics" in md
        assert "species accuracy" in md
        assert "## §12.3 target verdicts" in md

    def test_render_respects_line_length_budget(self, tmp_path):
        """MD013（≤200 列）：多 FP 株的清单行必须截断，完整数据在 metrics.json。"""
        many_fp = tuple(f"gene{i:03d}" for i in range(60))
        evals = [
            evaluate(
                _gold(tmp_path, _exp("SAM-A", amr_genes=[])),
                _facts("SAM-A", amr_genes=many_fp),
            )
        ]
        md = render_markdown(aggregate(evals), evals)
        assert all(len(line) <= 200 for line in md.splitlines())
        assert "+41 more" in md  # 7 字符名+2 分隔：19 个后超预算，余 41 折叠
