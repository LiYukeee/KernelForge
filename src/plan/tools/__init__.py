"""PLAN Agent 可使用的工具。"""

from typing import Any

__all__ = ["build_plan_tools", "get_system_info"]


def __getattr__(name: str) -> Any:
    """按需导入工具，避免执行子模块前被包初始化提前加载。"""
    if name == "build_plan_tools":
        from src.plan.tools.file_tools import build_plan_tools

        globals()[name] = build_plan_tools
        return build_plan_tools
    if name == "get_system_info":
        from src.plan.tools.get_system_info import get_system_info

        globals()[name] = get_system_info
        return get_system_info
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
