"""基于 LangChain callback 的 Agent 实时终端输出。"""

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


_MAX_TOOL_OUTPUT_CHARS = 500
_OMISSION_MARKER = "\n.....................\n"


class AgentOutputCallback(BaseCallbackHandler):
    """实时打印 DeepSeek 适配器标准化后的思考、回答和工具事件。"""

    def __init__(self) -> None:
        self._section: str | None = None
        self._tool_name: str | None = None

    def on_llm_new_token(
        self,
        token: str,
        *,
        chunk: Any = None,
        **kwargs: Any,
    ) -> None:
        """打印模型流中的 reasoning 和 text 内容块。"""
        message = getattr(chunk, "message", None)
        for block in getattr(message, "content_blocks", []):
            if block.get("type") == "reasoning":
                self._write("思考过程", block.get("reasoning", ""))
            elif block.get("type") == "text":
                self._write("模型输出", block.get("text", ""))

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """结束一次模型输出。"""
        self._close_section()

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """打印工具名称和输入。"""
        self._close_section()
        self._tool_name = serialized.get("name", "unknown")
        print(f"[工具调用] {self._tool_name}", flush=True)
        print(input_str, flush=True)

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        """打印工具返回值，过长时省略中间内容。"""
        output_text = str(output)
        if len(output_text) > _MAX_TOOL_OUTPUT_CHARS:
            visible_chars = _MAX_TOOL_OUTPUT_CHARS - len(_OMISSION_MARKER)
            head_chars = (visible_chars + 1) // 2
            tail_chars = visible_chars // 2
            output_text = (
                output_text[:head_chars]
                + _OMISSION_MARKER
                + output_text[-tail_chars:]
            )

        print(f"[工具结果] {self._tool_name or 'unknown'}", flush=True)
        print(output_text, flush=True)
        self._tool_name = None

    def _write(self, section: str, text: str) -> None:
        if not text:
            return
        if self._section != section:
            self._close_section()
            print(f"[{section}]", flush=True)
            self._section = section
        print(text, end="", flush=True)

    def _close_section(self) -> None:
        if self._section is not None:
            print()
            self._section = None
