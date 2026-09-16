"""PLAN Agent 的非文件系统工具。"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool

from src.base.tools.bench import build_bench_tool
from src.base.tools.get_system_info import get_system_info
from src.base.tools.profile import build_profile_tool


def build_plan_tools(target_path: Path) -> list[BaseTool]:
    """创建系统信息、benchmark 和 profiler 工具，并绑定到 TARGET。"""
    return [
        get_system_info,
        build_bench_tool(target_path),
        build_profile_tool(target_path),
    ]
