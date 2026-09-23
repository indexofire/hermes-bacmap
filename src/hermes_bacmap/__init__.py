"""hermes_bacmap plugin — registration."""

import logging
from typing import Any

from .tools.registry import _TOOL_REGISTRY

logger = logging.getLogger(__name__)


def register(ctx: Any) -> None:
    """Wire schemas to handlers and register with the Hermes tool registry."""
    for name, schema, handler in _TOOL_REGISTRY:
        ctx.register_tool(name=name, toolset="bioinfo", schema=schema, handler=handler)

    # Bundle skills with common pipeline guidance.
    # Skills live at <project_root>/skills/ — two levels up from this file
    # (src/hermes_bacmap/__init__.py → ../../skills/).
    from pathlib import Path

    skills_dir = Path(__file__).resolve().parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)

    logger.info("hermes_bacmap plugin registered %d tools", len(_TOOL_REGISTRY))

    import os

    from .config import SPECIES_DB_DIR

    manifests = SPECIES_DB_DIR / "manifests"
    if not os.environ.get("BACMAP_SKIP_SETUP_HINT") and not any(manifests.glob("*.json")):
        print(
            "[hermes-bacmap] 尚未部署鉴定数据库（当前仅 marker 靶基因模式）。"
            "对话中说「安装 ANI 鉴定库」即可用 bio_db_setup 选择档位，"
            "或 CLI 执行: pixi run setup"
        )
