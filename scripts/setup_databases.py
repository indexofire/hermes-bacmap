#!/usr/bin/env python3
"""Interactive database tier orchestrator.

Lists available species-identification database tiers with size/RAM
requirements, then delegates to the per-database download scripts
(scripts/download_db_<name>.py). Tiers whose scripts are not yet delivered
(the A/B/C phases of docs/plans/species-id/) are reported clearly instead
of failing silently.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

TIERS: dict[str, dict] = {
    "none": {"size": "0（仅 marker 靶基因）", "scripts": []},
    "instant": {
        "size": "159 MB（Mash sketch，社区维护）",
        "scripts": ["download_db_mash_refseq.py"],
    },
    "mini": {
        "size": "1-2 GB（RefSeq 精选面板 + skani）",
        "scripts": ["download_db_refseq_panel.py"],
    },
    "sourmash": {
        "size": "3.7 GB（sourmash GTDB reps）",
        "scripts": ["download_db_sourmash_gtdb.py"],
    },
    "full": {
        "size": "30 GB 下载 / 50 GB 解压（skani 官方 GTDB，查询需 <30GB RAM）",
        "scripts": ["download_db_skani_gtdb.py"],
    },
    "standard": {
        "size": "101 GB（GTDB-Tk R232 98GB + CheckM2 3GB，classify 需 >=140GB RAM）",
        "scripts": ["download_db_gtdbtk.py", "download_db_checkm2.py"],
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", required=True, choices=sorted(TIERS))
    parser.add_argument("--yes", action="store_true", help="Skip confirmation")
    parser.add_argument("--scripts-dir", type=Path, default=ROOT / "scripts")
    args = parser.parse_args()

    meta = TIERS[args.tier]
    print(f"tier={args.tier}  体积: {meta['size']}")

    if args.tier == "none":
        print("未选择任何数据库 — 仅使用 marker 靶基因鉴定（species_mode=simple）")
        return 0

    missing = [s for s in meta["scripts"] if not (args.scripts_dir / s).exists()]
    if missing:
        for s in missing:
            print(f"❌ 下载脚本未就绪: {s}（对应方案 A/B/C 阶段交付，见 docs/plans/species-id/）")
        return 2

    if not args.yes:
        answer = input(f"确认下载 {args.tier} 档（{meta['size']}）? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("已取消")
            return 1

    for script in meta["scripts"]:
        result = subprocess.run([sys.executable, str(args.scripts_dir / script)])
        if result.returncode != 0:
            print(f"❌ {script} 失败 (exit {result.returncode})")
            return 1
    print(f"\n✓ tier={args.tier} 安装完成 — 可用 species_mode 见 docs/plans/species-id/README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
