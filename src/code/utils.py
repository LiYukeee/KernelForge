"""CODE Agent 的无状态辅助函数。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_ROUND_DIR_PATTERN = re.compile(r"round_(\d+)$")
_BENCH_TOOL_NAME = "bench"


def _message_text(message: Any) -> str:
    """提取 LangChain 消息文本，并兼容测试替身。"""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return str(content)


def _last_bench_result(state: dict[str, Any]) -> str | None:
    """返回状态中最新一次 ``bench`` 工具调用的结果。"""
    for message in reversed(state.get("messages", [])):
        name = (
            message.get("name")
            if isinstance(message, dict)
            else getattr(message, "name", None)
        )
        if name == _BENCH_TOOL_NAME:
            result = _message_text(message).strip()
            if result:
                return result
    return None


def _benchmark_passed(result: str) -> bool:
    """仅依据 bench 工具的显式成功状态判断是否通过。"""
    return result.lstrip().startswith("BENCHMARK_SUCCEEDED")


def _latest_plan(target_path: Path) -> Path:
    """找到 PLAN Agent 生成的最新非空计划。"""
    candidates: list[tuple[int, Path]] = []
    exp_dir = target_path / "exp"
    if exp_dir.is_dir():
        for entry in exp_dir.iterdir():
            match = _ROUND_DIR_PATTERN.fullmatch(entry.name)
            plan_path = entry / "plan.md"
            if match and entry.is_dir() and plan_path.is_file():
                candidates.append((int(match.group(1)), plan_path))
    if not candidates:
        raise FileNotFoundError(
            f"TARGET 下没有找到 PLAN Agent 生成的计划：{target_path / 'exp' / 'round_N' / 'plan.md'}"
        )
    return max(candidates, key=lambda item: item[0])[1]


def _resolve_plan_path(target_path: Path, plan_path: str | Path | None) -> Path:
    """解析显式计划路径，或选择 TARGET 下的最新计划。"""
    if plan_path is None:
        return _latest_plan(target_path)
    resolved = Path(plan_path).expanduser()
    if not resolved.is_absolute():
        resolved = target_path / resolved
    resolved = resolved.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"计划文件不存在：{resolved}")
    _plan_round_number(resolved, target_path)
    return resolved


def _plan_round_number(plan_path: Path, target_path: Path) -> int:
    """校验计划位于 TARGET/exp/round_N/plan.md 并返回轮次。"""
    try:
        relative = plan_path.resolve().relative_to(target_path.resolve())
    except ValueError as exc:
        raise ValueError(f"计划文件必须位于 TARGET/exp/round_N：{plan_path}") from exc

    if len(relative.parts) != 3 or relative.parts[0] != "exp" or relative.name != "plan.md":
        raise ValueError(f"计划文件必须位于 TARGET/exp/round_N/plan.md：{plan_path}")
    match = _ROUND_DIR_PATTERN.fullmatch(relative.parts[1])
    if match is None:
        raise ValueError(f"计划目录名称必须使用 round_N 格式：{plan_path.parent}")
    return int(match.group(1))


def _relative_to_target(path: Path, target_path: Path) -> str:
    """返回供 Agent 文件工具使用的 TARGET 相对路径。"""
    try:
        return path.relative_to(target_path).as_posix()
    except ValueError:
        return str(path)
