"""从可编辑的 Markdown 模板构建 PLAN Agent 系统提示词。"""

from __future__ import annotations

from pathlib import Path


_PROMPT_PATH = Path(__file__).with_name("system_prompt.md")


def _read_prompt_template() -> str:
    """读取 Markdown 模板，避免把长提示词重复维护在 Python 字符串中。"""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_system_prompt(*, round_number: int) -> str:
    """将轮次编号注入 Markdown 系统提示词。"""
    prompt = _read_prompt_template()
    prompt = prompt.replace("{{ROUND_NUMBER}}", str(round_number))
    return prompt
