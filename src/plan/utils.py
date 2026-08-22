"""PLAN Agent 使用的路径、轮次和工具构建辅助函数。"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv


# TARGET 的相对路径语义需要与 scripts/bench.sh 保持一致，因此以 scripts 为基准目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
_ROUND_DIR_PATTERN = re.compile(r"round_(\d+)$")


def resolve_target_path(target: str | Path | None = None) -> Path:
    """解析并校验算子目录。

    优先使用调用者传入的 ``target``；未传入时读取 ``.env`` 中的
    ``TARGET``。相对路径按照 ``scripts/bench.sh`` 的约定，以项目的
    ``scripts`` 目录为基准进行解析。
    """
    load_dotenv(PROJECT_ROOT / ".env")
    raw_target = str(target) if target is not None else os.getenv("TARGET")
    if not raw_target or not raw_target.strip():
        raise ValueError("TARGET 未配置，请在 .env 中设置或显式传入 target。")

    # 支持 TARGET 中引用其他环境变量以及用户主目录符号。
    expanded_target = Path(os.path.expandvars(raw_target)).expanduser()
    if not expanded_target.is_absolute():
        expanded_target = SCRIPTS_DIR / expanded_target
    target_path = expanded_target.resolve()

    if not target_path.is_dir():
        raise FileNotFoundError(f"TARGET 目录不存在：{target_path}")

    # PLAN 阶段必须同时比较原始算子和当前优化算子，缺一不可。
    missing_files = [
        file_name
        for file_name in ("model.py", "model_new.py")
        if not (target_path / file_name).is_file()
    ]
    if missing_files:
        missing = ", ".join(missing_files)
        raise FileNotFoundError(f"TARGET 缺少必要文件：{missing}")

    return target_path


def select_round_number(target_path: Path) -> int:
    """选择本次 PLAN 使用的优化轮次。

    没有历史轮次时从第 1 轮开始；最新轮次尚未生成 ``plan.md`` 时
    继续复用该轮，避免模型调用失败后产生跳号；已有计划则进入下一轮。
    """
    exp_dir = target_path / "exp"
    rounds: list[tuple[int, Path]] = []
    if exp_dir.is_dir():
        for entry in exp_dir.iterdir():
            match = _ROUND_DIR_PATTERN.fullmatch(entry.name)
            if entry.is_dir() and match:
                rounds.append((int(match.group(1)), entry))

    if not rounds:
        return 1

    latest_number, latest_dir = max(rounds, key=lambda item: item[0])
    if (latest_dir / "plan.md").is_file():
        return latest_number + 1
    return latest_number
