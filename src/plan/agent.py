"""负责制定下一轮 GPU 算子优化方案的 LangChain Agent。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from src.base.agent import BaseAgent, print_all_enabled
from src.plan.system_prompt import build_system_prompt
from src.plan.tools import build_plan_tools
from src.plan.utils import resolve_target_path, select_round_number


DEFAULT_TASK = (
    "分析原始算子和当前优化算子，并返回本轮完整的 Markdown 优化计划。"
)


class PlanAgent(BaseAgent):
    """分析算子现状并制定优化计划，但不直接修改算子源码。"""

    def __init__(
        self,
        target: str | Path | None = None,
        *,
        model: Any | None = None,
    ) -> None:
        self.target_path = resolve_target_path(target)
        self.round_number = select_round_number(self.target_path)
        self.round_dir = self.target_path / "exp" / f"round_{self.round_number}"
        self.plan_path = self.round_dir / "plan.md"
        self.round_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(
            name="plan_agent",
            default_task=DEFAULT_TASK,
            system_prompt=build_system_prompt(round_number=self.round_number),
            tools=build_plan_tools(self.target_path),
            model=model,
        )

    def _finalize_result(self, result: dict[str, Any]) -> None:
        """将模型的最终回答作为本轮计划原子写入固定路径。"""
        messages = result.get("messages", [])
        if not messages or not isinstance(messages[-1], AIMessage):
            raise RuntimeError("PLAN Agent 未返回可保存的计划正文。")

        plan_text = messages[-1].text.strip()
        if not plan_text:
            raise RuntimeError("PLAN Agent 未返回可保存的计划正文。")

        temporary_path = self.plan_path.with_name(f".{self.plan_path.name}.tmp")
        temporary_path.write_text(plan_text.rstrip() + "\n", encoding="utf-8")
        temporary_path.replace(self.plan_path)

    def _validate_result(self, result: dict[str, Any]) -> None:
        """确认 PLAN 阶段已经生成本轮计划文件。"""
        if not self.plan_path.is_file() or self.plan_path.stat().st_size == 0:
            raise RuntimeError(f"PLAN Agent 未生成非空计划文件：{self.plan_path}")


def main() -> None:
    from rich import print as rprint

    plan_agent = PlanAgent()
    result = plan_agent.run()
    if not print_all_enabled():
        rprint(result)


if __name__ == "__main__":
    main()
