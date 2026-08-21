"""PLAN Agent 的文件搜索与读取工具。"""

from __future__ import annotations

from pathlib import Path

from langchain_community.tools.file_management import (
    FileSearchTool,
    ListDirectoryTool,
    ReadFileTool,
)
from langchain_core.tools import BaseTool

from src.plan.tools.get_system_info import get_system_info


def build_plan_tools(target_path: Path) -> list[BaseTool]:
    """创建 PLAN Agent 的只读 LangChain 工具列表。

    搜索、目录浏览和读取工具的根目录固定为 TARGET，因此既可以读取
    算子源码，也可以读取 ``exp`` 下的历史计划和实验记录。计划文件由
    PlanAgent 在模型完成响应后写入，不向模型暴露文件写入工具。系统信息
    工具自动选择 GPU，并读取所选 GPU 和软件环境。
    """
    return [
        FileSearchTool(
            root_dir=str(target_path),
            name="search_target_files",
            description=(
                "递归搜索 TARGET 下的所有文件。dir_path 必须是相对 TARGET 的"
                "目录，默认使用 '.'；pattern 是文件名通配符，使用 '*' 可发现"
                "所有算子源码、历史计划和实验记录。"
            ),
        ),
        ListDirectoryTool(
            root_dir=str(target_path),
            name="list_target_directory",
            description=(
                "列出 TARGET 下指定目录的直接子项。dir_path 必须是相对 TARGET "
                "的路径，例如 '.'、'exp' 或 'exp/round_1'。"
            ),
        ),
        ReadFileTool(
            root_dir=str(target_path),
            name="read_target_file",
            description=(
                "读取 TARGET 下的 UTF-8 文本文件。file_path 必须是相对 TARGET "
                "的路径，可以读取任意层级的算子源码、benchmark 结果、历史计划"
                "和实验报告，例如 'model.py' 或 'exp/round_1/plan.md'。"
            ),
        ),
        get_system_info,
    ]
