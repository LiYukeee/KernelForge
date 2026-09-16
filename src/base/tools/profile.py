"""CODE Agent 用于运行优化模型 profiler 的工具。"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from langchain_core.tools import BaseTool, tool


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROFILE_SCRIPT = _PROJECT_ROOT / "scripts" / "profile.sh"
_DEFAULT_WARMUP = 200
_DEFAULT_ITERATIONS = 10
_MAX_OUTPUT_CHARS = 16_000
_TERMINATE_GRACE_SECONDS = 5


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _trim_output(output: str) -> str:
    output = output.strip()
    if len(output) <= _MAX_OUTPUT_CHARS:
        return output or "(the profiling process produced no output)"

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
    lines = [f"PROFILE_{status.upper()}", f"Elapsed: {elapsed_seconds:.1f}s"]
    if returncode is not None:
        lines.append(f"Exit code: {returncode}")
    if diagnosis:
        lines.append(f"Diagnosis: {diagnosis}")
    lines.extend(("Output:", _trim_output(output)))
    return "\n".join(lines)


def _stop_process_group(process: subprocess.Popen[str]) -> str:
    """Terminate profile.sh and its Python children after a timeout."""
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


def run_profile(
    timeout_seconds: int = 600,
    warmup: int = _DEFAULT_WARMUP,
    iterations: int = _DEFAULT_ITERATIONS,
    v1_file: str | None = None,
    target_dir: str | None = None,
) -> str:
    """Run ``scripts/profile.sh`` and return an agent-readable diagnostic."""
    if timeout_seconds <= 0:
        return "PROFILE_ARGUMENT_ERROR\ntimeout_seconds must be greater than zero."
    if warmup < 0:
        return "PROFILE_ARGUMENT_ERROR\nwarmup must be non-negative."
    if iterations <= 0:
        return "PROFILE_ARGUMENT_ERROR\niterations must be greater than zero."
    if not _PROFILE_SCRIPT.is_file():
        return f"PROFILE_ENVIRONMENT_ERROR\nProfile script not found: {_PROFILE_SCRIPT}"

    command = [
        "bash",
        str(_PROFILE_SCRIPT),
        "--warmup",
        str(warmup),
        "--iterations",
        str(iterations),
    ]
    if v1_file is not None:
        command.extend(("--v1-file", v1_file))

    process_env = None
    if target_dir is not None:
        process_env = os.environ.copy()
        process_env["PROFILE_TARGET_OVERRIDE"] = str(Path(target_dir).resolve())

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
            diagnosis=f"Could not start scripts/profile.sh: {exc}",
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
            diagnosis=f"The profiling process exceeded its {timeout_seconds}-second timeout.",
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
def profile(
    timeout_seconds: int = 600,
    warmup: int = _DEFAULT_WARMUP,
    iterations: int = _DEFAULT_ITERATIONS,
) -> str:
    """对 model_new.py 进行 torch.profiler 分析。

    profiler 会先执行 ``warmup`` 次预热，再采集 ``iterations`` 次调用，
    并将按 CUDA 总耗时排序的前十项写入
    ``TARGET/bench_output/torch_profile_latest.txt``。模型文件路径由控制器绑定，
    工具只返回脚本的原始诊断和耗时，不猜测失败原因。
    """
    return run_profile(timeout_seconds, warmup, iterations)


def build_profile_tool(target_path: Path) -> BaseTool:
    """创建固定使用 ``TARGET/model_new.py`` 的 profiler 工具。"""
    resolved_target = target_path.resolve()
    v1_file = str(resolved_target / "model_new.py")

    @tool("profile", description=profile.description)
    def target_profile(
        timeout_seconds: int = 600,
        warmup: int = _DEFAULT_WARMUP,
        iterations: int = _DEFAULT_ITERATIONS,
    ) -> str:
        return run_profile(
            timeout_seconds,
            warmup,
            iterations,
            v1_file=v1_file,
            target_dir=str(resolved_target),
        )

    return target_profile


if __name__ == "__main__":
    print(run_profile())
