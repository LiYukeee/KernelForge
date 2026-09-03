"""get_system_info 工具：在 benchmark 解释器（.env 的 PYTHON_BIN）中收集环境信息。

这个 langchain 工具的宿主进程运行在 conda ``lang`` 环境，它没有安装
PyTorch/triton，无法如实报告实际 benchmark 环境的状态。因此本工具不是就地
收集，而是通过 ``scripts/get_system_info.sh`` 派生一个子进程，用 ``.env``
里的 ``PYTHON_BIN``（torch_new 环境）运行 ``scripts/get_system_info.py``，
然后解析子进程 stdout 的 JSON。这样 agent 看到的 Python/PyTorch/CUDA/MACA
信息与真正运行 ``scripts/bench.py`` 的环境完全一致。
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

_SCRIPT_DIR = Path(__file__).resolve().parents[3] / "scripts"
_WRAPPER = _SCRIPT_DIR / "get_system_info.sh"
_TERMINATE_GRACE_SECONDS = 5


def _stop_subprocess(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
    except Exception:
        pass
    try:
        process.communicate(timeout=_TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except Exception:
            pass
        process.communicate()


def _collect_from_subprocess(timeout_seconds: int) -> dict[str, Any]:
    """在 torch_new 解释器里运行收集脚本，并把 stdout 解析为结构化结果。"""
    if not _WRAPPER.is_file():
        return {
            "available": False,
            "error": f"Collector wrapper not found: {_WRAPPER}",
        }

    process_env = os.environ.copy()
    try:
        process = subprocess.Popen(
            ["bash", str(_WRAPPER)],
            cwd=_WRAPPER.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=process_env,
        )
    except OSError as exc:
        return {
            "available": False,
            "error": f"Could not start scripts/get_system_info.sh: {exc}",
        }

    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _stop_subprocess(process)
        return {
            "available": False,
            "error": (
                f"System-info collection exceeded its {timeout_seconds}-second "
                "timeout."
            ),
        }

    if process.returncode != 0:
        return {
            "available": False,
            "returncode": process.returncode,
            "error": (stderr or stdout or "collector exited with a non-zero status"),
        }

    # The standalone script prints JSON as its sole stdout payload; auto-choose
    # diagnostics go to stderr, which we surface only if JSON parsing fails.
    try:
        info: dict[str, Any] = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {
            "available": False,
            "error": f"Collector did not return valid JSON: {exc}",
            "stderr": stderr,
        }
    info.setdefault("available", True)
    return info


@tool
def get_system_info(timeout_seconds: int = 120) -> dict[str, Any]:
    """获取当前优化环境的系统、所选 GPU、CUDA/MACA 和 PyTorch 环境信息。

    此工具在 ``.env`` 的 ``PYTHON_BIN``（torch_new，包含 PyTorch）解释器中
    收集信息——也就是实际运行 benchmark 的同一个环境，因此返回的解释器版本、
    PyTorch 构建和加速后端状态始终与 bench 一致。

    它不接收业务参数，``timeout_seconds`` 用于控制子进程收集的等待上限。
    它会先自动选择显存占用最低的 GPU，随后只查询所选 GPU 的详细信息，不会
    返回其他 GPU 的详细信息或写入文件。制定依赖硬件特性的优化计划前应调用它。
    """
    if timeout_seconds <= 0:
        return {
            "available": False,
            "error": "timeout_seconds must be greater than zero.",
        }
    return _collect_from_subprocess(timeout_seconds)


if __name__ == "__main__":
    from rich import print as rich_print

    rich_print(get_system_info.invoke({}))