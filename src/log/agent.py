"""归档当前实现并维护累计实验记录的 LangChain Agent。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.base.agent import BaseAgent, print_all_enabled
from src.base.tools.target_filesystem import build_target_filesystem
from src.code.utils import _plan_round_number, _resolve_plan_path
from src.log.system_prompt import build_system_prompt
from src.log.utils import BenchmarkRecord, parse_benchmark_log
from src.plan.utils import resolve_target_path


DEFAULT_TASK = "整理当前轮次的实验结果，更新累计经验和实验汇总。"
_SUMMARY_COLUMNS = ("round", "ModelNew 延迟", "加速比", "正确性", "简单描述")
_TABLE_SEPARATOR = re.compile(r"^:?-{3,}:?$")


def _table_cells(line: str) -> tuple[str, ...] | None:
    """解析 Markdown 表格行，并去掉表头可能使用的粗体标记。"""
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return tuple(
        cell.strip().strip("*").strip() for cell in stripped[1:-1].split("|")
    )


def _validate_summary(
    summary_text: str,
    round_number: int,
    benchmark_record: BenchmarkRecord | None = None,
) -> None:
    """校验汇总表头、分隔行和当前轮次唯一记录。"""
    lines = [line for line in summary_text.splitlines() if line.strip()]
    if len(lines) < 3:
        raise RuntimeError("LOG Agent 生成的 exp/summary.md 不是完整 Markdown 表格。")

    header = _table_cells(lines[0])
    separator = _table_cells(lines[1])
    if header != _SUMMARY_COLUMNS:
        raise RuntimeError(
            "LOG Agent 生成的 exp/summary.md 表头不符合要求："
            + " | ".join(_SUMMARY_COLUMNS)
        )
    if separator is None or len(separator) != len(_SUMMARY_COLUMNS) or not all(
        _TABLE_SEPARATOR.fullmatch(cell) for cell in separator
    ):
        raise RuntimeError("LOG Agent 生成的 exp/summary.md 缺少合法的表格分隔行。")

    rows = [_table_cells(line) for line in lines[2:]]
    if any(row is None or len(row) != len(_SUMMARY_COLUMNS) for row in rows):
        raise RuntimeError("LOG Agent 生成的 exp/summary.md 包含格式错误的数据行。")

    round_values: list[int] = []
    for row in rows:
        assert row is not None
        try:
            row_round = int(row[0])
        except ValueError as exc:
            raise RuntimeError("实验汇总的 round 字段必须是不带前缀的整数。") from exc
        if row[0] != str(row_round) or row_round <= 0:
            raise RuntimeError("实验汇总的 round 字段必须是不带前缀的正整数。")
        round_values.append(row_round)
    if round_values != sorted(set(round_values)):
        raise RuntimeError("实验汇总必须按 round 升序排列，且每轮只能有一条记录。")

    current_rows = [
        row for row in rows if row is not None and row[0] == str(round_number)
    ]
    if len(current_rows) != 1:
        raise RuntimeError(
            f"LOG Agent 必须为 round {round_number} 生成且只生成一条实验记录。"
        )
    if any(not cell for cell in current_rows[0]):
        raise RuntimeError(f"LOG Agent 生成的 round {round_number} 实验记录存在空字段。")
    if current_rows[0][3] not in {"通过", "失败"}:
        raise RuntimeError("实验汇总的正确性字段必须是“通过”或“失败”。")
    if benchmark_record is not None:
        expected_metrics = (
            benchmark_record.model_new_latency,
            benchmark_record.speedup,
            benchmark_record.correctness,
        )
        if current_rows[0][1:4] != expected_metrics:
            raise RuntimeError(
                f"round {round_number} 的实验指标与 bench_latest.log 不一致。"
            )


class LogAgent(BaseAgent):
    """归纳实验教训、累计指标，并保存本轮 ``model_new.py`` 快照。"""

    def __init__(
        self,
        target: str | Path | None = None,
        *,
        plan_path: str | Path | None = None,
        model: Any | None = None,
    ) -> None:
        self.target_path = resolve_target_path(target)
        self.plan_path = _resolve_plan_path(self.target_path, plan_path)
        self.round_number = _plan_round_number(self.plan_path, self.target_path)
        self.round_dir = self.target_path / "exp" / f"round_{self.round_number}"
        self.archive_path = self.round_dir / "model_new.py"
        self.lessons_path = self.target_path / "exp" / "lessons.md"
        self.summary_path = self.target_path / "exp" / "summary.md"
        self.benchmark_record = parse_benchmark_log(
            self.target_path / "bench_output" / "bench_latest.log"
        )

        filesystem_access = build_target_filesystem(
            self.target_path,
            role="log",
            round_number=self.round_number,
        )
        self.filesystem_backend = filesystem_access.backend

        super().__init__(
            name="log_agent",
            default_task=DEFAULT_TASK,
            system_prompt=build_system_prompt(
                round_number=self.round_number,
                model_new_latency=self.benchmark_record.model_new_latency,
                speedup=self.benchmark_record.speedup,
                correctness=self.benchmark_record.correctness,
            ),
            tools=[],
            middleware=[filesystem_access.middleware],
            model=model,
        )

    def _finalize_result(self, result: dict[str, Any]) -> None:
        """在模型完成记录后，原子归档当前优化实现。"""
        self.filesystem_backend.atomic_copy(
            "/model_new.py",
            f"/exp/round_{self.round_number}/model_new.py",
        )

    def _validate_result(self, result: dict[str, Any]) -> None:
        """确认累计文档和本轮源码归档完整有效。"""
        model_new_path = self.target_path / "model_new.py"
        if not self.archive_path.is_file():
            raise RuntimeError(f"LOG Agent 未归档当前实现：{self.archive_path}")
        if self.archive_path.read_bytes() != model_new_path.read_bytes():
            raise RuntimeError(
                f"LOG Agent 的模型归档与当前 model_new.py 不一致：{self.archive_path}"
            )

        if not self.lessons_path.is_file():
            raise RuntimeError(f"LOG Agent 未生成累计经验文件：{self.lessons_path}")
        lessons_text = self.lessons_path.read_text(encoding="utf-8").strip()
        if not lessons_text:
            raise RuntimeError(f"LOG Agent 生成的累计经验文件为空：{self.lessons_path}")

        if not self.summary_path.is_file():
            raise RuntimeError(f"LOG Agent 未生成实验汇总文件：{self.summary_path}")
        _validate_summary(
            self.summary_path.read_text(encoding="utf-8"),
            self.round_number,
            self.benchmark_record,
        )


def main() -> None:
    from rich import print as rprint

    log_agent = LogAgent()
    result = log_agent.run()
    if not print_all_enabled():
        rprint(result)


if __name__ == "__main__":
    main()
