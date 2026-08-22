"""PLAN Agent 的非文件系统工具。"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool

from src.base.tools.bench import build_bench_tool
from src.base.tools.get_system_info import get_system_info


def build_plan_tools(target_path: Path) -> list[BaseTool]:
    """创建系统信息工具和绑定到 TARGET 的 benchmark 工具。"""
    return [
        get_system_info,
        build_bench_tool(target_path),
    ]
