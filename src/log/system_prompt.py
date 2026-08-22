"""从可编辑的 Markdown 模板构建 LOG Agent 系统提示词。"""

from __future__ import annotations

from pathlib import Path


_PROMPT_PATH = Path(__file__).with_name("system_prompt.md")


def _read_prompt_template() -> str:
    """读取 LOG Agent 的 Markdown 提示词模板。"""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_system_prompt(
    *,
    round_number: int,
    model_new_latency: str,
    speedup: str,
    correctness: str,
) -> str:
    """将当前轮次和控制器解析出的 benchmark 指标注入提示词。"""
    replacements = {
        "{{ROUND_NUMBER}}": str(round_number),
        "{{MODEL_NEW_LATENCY}}": model_new_latency,
        "{{SPEEDUP}}": speedup,
        "{{CORRECTNESS}}": correctness,
    }
    prompt = _read_prompt_template()
    for marker, value in replacements.items():
        prompt = prompt.replace(marker, value)
    return prompt
