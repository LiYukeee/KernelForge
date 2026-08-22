"""各阶段 Agent 共用的 LangChain 执行基类。"""

from __future__ import annotations

import os
from typing import Any, Sequence

from langchain.agents import create_agent

from src.base.model import load_model
from src.base.streaming import AgentOutputCallback


_TRUE_VALUES = {"1", "true", "yes", "on"}


def print_all_enabled() -> bool:
    """判断是否需要实时打印 Agent 的完整执行过程。"""
    return os.getenv("PRINT_ALL", "false").strip().lower() in _TRUE_VALUES


class BaseAgent:
    """封装所有 Agent 共用的创建、调用和流式输出逻辑。"""

    def __init__(
        self,
        *,
        name: str,
        default_task: str,
        system_prompt: str,
        tools: Sequence[Any],
        middleware: Sequence[Any] = (),
        model: Any | None = None,
    ) -> None:
        self.name = name
        self.default_task = default_task
        self.system_prompt = system_prompt
        self.tools = list(tools)
        self.middleware = list(middleware)
        self.model = (
            model if model is not None else load_model(streaming=print_all_enabled())
        )
        self.agent = create_agent(
            model=self.model,
            tools=self.tools,
            middleware=self.middleware,
            system_prompt=self.system_prompt,
            name=self.name,
        )

    def invoke(
        self,
        instruction: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """调用 Agent，并返回包含全部消息的最终状态。"""
        task = self.default_task if instruction is None else instruction
        inputs = {"messages": [{"role": "user", "content": task}]}
        if print_all_enabled():
            config = dict(kwargs.get("config") or {})
            callbacks = list(config.get("callbacks") or [])
            config["callbacks"] = [*callbacks, AgentOutputCallback()]
            kwargs["config"] = config
        result = self.agent.invoke(inputs, **kwargs)

        self._finalize_result(result)
        self._validate_result(result)
        return result

    def run(self, instruction: str | None = None, **kwargs: Any) -> Any:
        """运行 Agent，并返回最后一条助手消息中的最终回答。"""
        result = self.invoke(instruction, **kwargs)
        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError(f"{self.name} 未返回任何消息。")
        return messages[-1].text

    def _finalize_result(self, result: dict[str, Any]) -> None:
        """处理阶段产物；不需要持久化结果的 Agent 可使用默认空实现。"""
        return None

    def _validate_result(self, result: dict[str, Any]) -> None:
        """校验阶段结果；没有额外约束的 Agent 可使用默认空实现。"""
        return None
