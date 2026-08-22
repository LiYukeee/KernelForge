"""从可编辑的 Markdown 模板构建 CODE Agent 系统提示词。"""

from __future__ import annotations

from pathlib import Path


_PROMPT_PATH = Path(__file__).with_name("system_prompt.md")
DEFAULT_TASK = "根据计划完成当前轮次的算子优化，并通过 benchmark 验证修改结果。"


def _read_prompt_template() -> str:
    """读取 Markdown 模板，避免把长提示词重复维护在 Python 字符串中。"""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_system_prompt(
    *,
    plan_relative: str
) -> str:
    """将运行时路径和 benchmark 参数注入 Markdown 系统提示词。"""
    replacements = {
        "{{PLAN_VIRTUAL}}": "/" + plan_relative.lstrip("/")
    }
    prompt = _read_prompt_template()
    for marker, value in replacements.items():
        prompt = prompt.replace(marker, value)
    return prompt
