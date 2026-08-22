"""基于 Deep Agents 的算子代码执行与 benchmark 修复 Agent。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import TodoListMiddleware

from src.base.agent import print_all_enabled
from src.base.model import load_model
from src.base.streaming import AgentOutputCallback
from src.code.system_prompt import DEFAULT_TASK, build_system_prompt
from src.code.tools.bench import bench
from src.code.tools.filesystem import build_code_filesystem_middleware
from src.code.utils import (
    _benchmark_passed,
    _last_bench_result,
    _message_text,
    _relative_to_target,
    _resolve_plan_path,
)
from src.plan.utils import resolve_target_path


MAX_REPAIR_ATTEMPTS = 5


class CodeAgent:
    """执行 PLAN Agent 的计划，并在 benchmark 失败后自动修复代码。

    每次修复都是一次新的 Deep Agent 调用。benchmark 结果由工具原样返回，
    控制器只识别 ``BENCHMARK_SUCCEEDED`` 这一成功标记，不对失败原因做猜测。
    """

    def __init__(
        self,
        target: str | Path | None = None,
        *,
        plan_path: str | Path | None = None,
        model: Any | None = None,
        max_repair_attempts: int = MAX_REPAIR_ATTEMPTS,
        bench_mode: str = "full",
        bench_timeout_seconds: int = 600,
    ) -> None:
        if max_repair_attempts < 0:
            raise ValueError("max_repair_attempts 不能小于 0。")
        if bench_mode not in {"full", "quick", "correctness"}:
            raise ValueError(f"不支持的 benchmark 模式：{bench_mode!r}")
        if bench_timeout_seconds <= 0:
            raise ValueError("bench_timeout_seconds 必须大于 0。")

        self.target_path = resolve_target_path(target)
        self.plan_path = _resolve_plan_path(self.target_path, plan_path)
        self.max_repair_attempts = min(max_repair_attempts, MAX_REPAIR_ATTEMPTS)
        self.bench_mode = bench_mode
        self.bench_timeout_seconds = bench_timeout_seconds
        self.model = model if model is not None else load_model(streaming=print_all_enabled())
        filesystem_backend = FilesystemBackend(root_dir=self.target_path)
        self.agent = create_deep_agent(
            model=self.model,
            tools=[bench],
            middleware=[
                build_code_filesystem_middleware(filesystem_backend),
                TodoListMiddleware(),
            ],
            backend=filesystem_backend,
            system_prompt=build_system_prompt(
                target_path=self.target_path,
                plan_relative=_relative_to_target(self.plan_path, self.target_path),
                bench_mode=self.bench_mode,
                bench_timeout_seconds=self.bench_timeout_seconds,
            ),
            name="code_agent",
        )

    def invoke(self, instruction: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """执行一次 Deep Agent 调用并返回完整状态。"""
        task = DEFAULT_TASK if instruction is None else instruction
        config = dict(kwargs.pop("config", {}) or {})
        if print_all_enabled():
            callbacks = list(config.get("callbacks") or [])
            config["callbacks"] = [*callbacks, AgentOutputCallback()]
        if config:
            kwargs["config"] = config
        return self.agent.invoke(
            {"messages": [{"role": "user", "content": task}]},
            **kwargs,
        )

    def _run_bench_fallback(self) -> str:
        """Run benchmark if the model ended a turn without calling its tool."""
        return bench.invoke(
            {
                "mode": self.bench_mode,
                "timeout_seconds": self.bench_timeout_seconds,
                "v0_file": str(self.target_path / "model.py"),
                "v1_file": str(self.target_path / "model_new.py"),
            }
        )

    def run(self, instruction: str | None = None, **kwargs: Any) -> str:
        """执行计划，并最多进行五次由 benchmark 诊断驱动的修复。"""
        plan_relative = _relative_to_target(self.plan_path, self.target_path)
        initial_task = (
            instruction
            or f"{DEFAULT_TASK}\n本轮计划文件是 `{plan_relative}`。完成计划后按系统要求调用 benchmark。"
        )
        state = self.invoke(initial_task, **kwargs)
        benchmark_result = _last_bench_result(state) or self._run_bench_fallback()
        repair_attempts = 0
        last_state = state

        while (
            not _benchmark_passed(benchmark_result)
            and repair_attempts < self.max_repair_attempts
        ):
            repair_attempts += 1
            repair_task = f"""上一轮修改后的 benchmark 没有通过。请读取当前工作区和计划，针对下面的原始 benchmark 输出修复当前自定义实现；必要时在 Triton 与 CUDA 路线之间通过源码修改切换，然后再次调用 bench 一次。

这是第 {repair_attempts}/{self.max_repair_attempts} 次修复。不要修改 `model.py` 或 `.env`，不要只给出建议，必须写入代码并验证。不得加入 PyTorch/ATen 运行时退化路径，不得用可用性标志、守卫或宽泛异常处理隐藏自定义 kernel 的错误。

原始 benchmark 输出：
{benchmark_result}
"""
            last_state = self.invoke(repair_task, **kwargs)
            benchmark_result = _last_bench_result(last_state) or self._run_bench_fallback()

        if _benchmark_passed(benchmark_result):
            status = "CODE_AGENT_SUCCEEDED"
        else:
            status = "CODE_AGENT_FAILED"
            benchmark_result = (
                f"{benchmark_result}\n\n已达到最多 {self.max_repair_attempts} 次修复，停止继续修改。"
            )

        final_messages = last_state.get("messages", [])
        final_report = _message_text(final_messages[-1]) if final_messages else ""
        report_parts = [
            status,
            f"Repair attempts: {repair_attempts}",
            "Benchmark result:",
            benchmark_result,
        ]
        if final_report.strip():
            report_parts.extend(("Agent report:", final_report.strip()))
        return "\n".join(report_parts)


def main() -> None:
    from rich import print as rprint

    result = CodeAgent().run()
    if not print_all_enabled():
        rprint(result)


if __name__ == "__main__":
    main()
