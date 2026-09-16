"""CODE Agent 用于运行 GPU benchmark 的工具。"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Literal

from langchain_core.tools import BaseTool, tool


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_BENCH_SCRIPT = _PROJECT_ROOT / "scripts" / "bench.sh"
_VALID_MODES = {"full", "quick", "correctness"}
_MAX_OUTPUT_CHARS = 16_000
_TERMINATE_GRACE_SECONDS = 5


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _trim_output(output: str) -> str:
    """Keep compiler diagnostics useful without flooding an agent context."""
    output = output.strip()
    if len(output) <= _MAX_OUTPUT_CHARS:
        return output or "(the benchmark process produced no output)"

    head_chars = _MAX_OUTPUT_CHARS // 4
    tail_chars = _MAX_OUTPUT_CHARS - head_chars
    omitted = len(output) - _MAX_OUTPUT_CHARS
    return (
        f"{output[:head_chars]}\n\n"
        f"... ({omitted} characters omitted; the final diagnostic is retained) ...\n\n"
        f"{output[-tail_chars:]}"
    )


def _format_result(
    *,
    status: str,
    elapsed_seconds: float,
    output: str,
    returncode: int | None = None,
    diagnosis: str | None = None,
) -> str:
    lines = [
        f"BENCHMARK_{status.upper()}",
        f"Elapsed: {elapsed_seconds:.1f}s",
    ]
    if returncode is not None:
        lines.append(f"Exit code: {returncode}")
    if diagnosis:
        lines.append(f"Diagnosis: {diagnosis}")
    lines.extend(("Output:", _trim_output(output)))
    return "\n".join(lines)


def _stop_process_group(process: subprocess.Popen[str]) -> str:
    """Terminate bench.sh and its Python/tee children after a timeout."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    try:
        stdout, _ = process.communicate(timeout=_TERMINATE_GRACE_SECONDS)
        return _as_text(stdout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, _ = process.communicate()
        return _as_text(stdout)


def run_bench(
    mode: Literal["full", "quick", "correctness"] = "full",
    timeout_seconds: int = 600,
    v0_file: str | None = None,
    v1_file: str | None = None,
    target_dir: str | None = None,
) -> str:
    """Run ``scripts/bench.sh`` and return an agent-readable diagnostic."""
    if mode not in _VALID_MODES:
        return (
            "BENCHMARK_ARGUMENT_ERROR\n"
            f"Unsupported mode: {mode!r}. Choose one of: {', '.join(sorted(_VALID_MODES))}."
        )
    if timeout_seconds <= 0:
        return "BENCHMARK_ARGUMENT_ERROR\ntimeout_seconds must be greater than zero."
    if not _BENCH_SCRIPT.is_file():
        return f"BENCHMARK_ENVIRONMENT_ERROR\nBenchmark script not found: {_BENCH_SCRIPT}"

    command = ["bash", str(_BENCH_SCRIPT), mode]
    if v0_file is not None:
        command.extend(("--v0-file", v0_file))
    if v1_file is not None:
        command.extend(("--v1-file", v1_file))
    process_env = None
    if target_dir is not None:
        process_env = os.environ.copy()
        process_env["BENCH_TARGET_OVERRIDE"] = str(Path(target_dir).resolve())

    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=_PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
            env=process_env,
        )
    except OSError as exc:
        return _format_result(
            status="environment_error",
            elapsed_seconds=time.monotonic() - started,
            diagnosis=f"Could not start scripts/bench.sh: {exc}",
            output="",
        )

    try:
        output, _ = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        partial_output = _as_text(exc.output)
        stopped_output = _stop_process_group(process)
        output = "\n".join(part for part in (partial_output, stopped_output) if part)
        return _format_result(
            status="timeout",
            elapsed_seconds=time.monotonic() - started,
            diagnosis=f"The benchmark exceeded its {timeout_seconds}-second timeout.",
            output=output,
        )

    elapsed_seconds = time.monotonic() - started
    output = _as_text(output)
    if process.returncode == 0:
        return _format_result(
            status="succeeded",
            elapsed_seconds=elapsed_seconds,
            output=output,
        )

    return _format_result(
        status="failed",
        elapsed_seconds=elapsed_seconds,
        returncode=process.returncode,
        output=output,
    )


@tool
def bench(
    mode: Literal["full", "quick", "correctness"] = "full",
    timeout_seconds: int = 600,
) -> str:
    """验证 model_new.py 的正确性并测量相对 model.py 的性能。

    验证流程：脚本固定随机种子加载 V0/V1 的 ``Model``、``get_init_inputs`` 和
    ``get_inputs``，自动选择加速设备，并让 V1 使用 V0 输入的克隆。随后分别执行
    一次 ``forward`` 并递归比较输出；浮点张量默认使用 ``atol=1e-2``、
    ``rtol=1e-2`` 且允许对应位置的 NaN，其他张量精确比较。正确性通过后才测量
    V0/V1 延迟：预热调用不计时，每个计时样本后同步设备，最终报告延迟中位数和
    ``speedup = v0_ms / v1_ms``。

    模式对应的性能采样次数：

    - ``correctness``：``warmup=0``、``repeat=1``，用于最快暴露加载、编译、
      运行或输出错误，仍会给出一次延迟样本；
    - ``quick``：``warmup=20``、``repeat=100``，用于开发中的性能筛选；
    - ``full``：``warmup=200``、``repeat=500``，用于最终稳定测量。

    重要的源码加载规则：benchmark 会解析并过滤 V0/V1 的模块 AST。顶层只保留
    ``import``/``from ... import ...``、类定义、同步/异步函数定义，以及值完全由
    字面量组成的赋值（常量和由常量组成的 tuple/list/set/dict，含一元正负数）。
    顶层函数调用、计算赋值、``try/except``、``if``、循环、``with`` 等可执行
    语句会被丢弃；必须执行的初始化应放进保留的函数或类方法中，CUDA 源码等配置
    应使用顶层字符串/数值字面量。不要依赖被过滤内容来导入 Triton、定义 kernel、
    设置可用性标志或选择实现路径。

    失败时工具原样返回脚本诊断、退出码和耗时，不在工具层猜测错误类型。V0/V1
    路径由控制器绑定，模型不能传入或覆盖宿主机文件路径。
    """
    return run_bench(mode, timeout_seconds)


def build_bench_tool(target_path: Path) -> BaseTool:
    """创建固定使用 TARGET/model.py 和 TARGET/model_new.py 的 benchmark 工具。"""
    resolved_target = target_path.resolve()
    v0_file = str(resolved_target / "model.py")
    v1_file = str(resolved_target / "model_new.py")

    @tool("bench", description=bench.description)
    def target_bench(
        mode: Literal["full", "quick", "correctness"] = "full",
        timeout_seconds: int = 600,
    ) -> str:
        return run_bench(
            mode,
            timeout_seconds,
            v0_file=v0_file,
            v1_file=v1_file,
            target_dir=str(resolved_target),
        )

    return target_bench


if __name__ == "__main__":
    print(run_bench())
