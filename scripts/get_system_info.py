"""Standalone system-info collector designed to run under the benchmark Python.

Run this via the benchmark interpreter (e.g. the ``PYTHON_BIN`` exported by
``.env``, which points at a PyTorch/triton-enabled env) so the reported
Python version, PyTorch, and accelerator state match the env that actually
runs ``scripts/bench.py``.

It has no dependency on langchain or python-dotenv, so it can also be launched
directly with ``$PYTHON_BIN scripts/get_system_info.py``. The default tensors/
torch import is deferred into ``_collect_torch_info``.

The process env is assumed to already be loaded (the tool spawns this through
a small ``.env``-sourcing wrapper). For direct runs we additionally parse a few
``KEY=value`` / ``export KEY=value`` lines from ``.env`` as a fallback, without
overriding env vars that are already set in the process.
"""

from __future__ import annotations

import csv
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_ENV_FILE = _SCRIPT_DIR.parent / ".env"


_NVIDIA_QUERY_FIELDS = [
    ("index", "index", int),
    ("uuid", "uuid", str),
    ("name", "name", str),
    ("driver_version", "driver_version", str),
    ("pci.bus_id", "pci_bus_id", str),
    ("compute_cap", "compute_capability", str),
    ("pstate", "performance_state", str),
    ("memory.total", "memory_total_mib", int),
    ("memory.used", "memory_used_mib", int),
    ("memory.free", "memory_free_mib", int),
    ("utilization.gpu", "gpu_utilization_percent", int),
    ("utilization.memory", "memory_utilization_percent", int),
    ("temperature.gpu", "temperature_c", int),
    ("power.draw", "power_draw_w", float),
    ("power.limit", "power_limit_w", float),
    ("clocks.current.sm", "sm_clock_mhz", int),
    ("clocks.current.memory", "memory_clock_mhz", int),
    ("clocks.max.sm", "max_sm_clock_mhz", int),
    ("clocks.max.memory", "max_memory_clock_mhz", int),
]

_TORCH_DEVICE_PROPERTIES = [
    "name",
    "major",
    "minor",
    "total_memory",
    "multi_processor_count",
    "warp_size",
    "max_threads_per_block",
    "max_threads_per_multi_processor",
    "shared_memory_per_block",
    "shared_memory_per_multiprocessor",
    "regs_per_block",
    "l2_cache_size",
    "memory_clock_rate",
    "memory_bus_width",
]


def _load_dotenv_fallback(env_file: Path) -> None:
    """Parse a selection of ``KEY=value`` / ``export KEY=value`` lines from
    ``.env`` into the process environment without overriding existing values.

    python-dotenv is not guaranteed to exist in the benchmark interpreter, so
    this small loader makes the script independently runnable. Comments and
    blank lines are skipped; unrecognized/empty keys are ignored.
    """
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'").strip()
        if not key:
            continue
        if key not in os.environ:
            os.environ[key] = value


def _run_command(command: list[str], timeout: int = 10) -> dict[str, Any]:
    """执行只读系统命令，并将成功或错误统一转换为字典。"""
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}

    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip()
        return {
            "ok": False,
            "returncode": completed.returncode,
            "error": error or "command failed without output",
        }
    return {"ok": True, "stdout": completed.stdout.strip()}


def _convert_nvidia_value(raw_value: str, converter: type) -> Any:
    """转换 nvidia-smi 字段，并将 N/A 统一表示为 None。"""
    value = raw_value.strip()
    if not value or value.lower() in {"n/a", "[n/a]", "not supported"}:
        return None
    try:
        return converter(value)
    except (TypeError, ValueError):
        return value


def _parse_nvidia_csv(output: str) -> list[dict[str, Any]]:
    """把 nvidia-smi CSV 输出解析为每块 GPU 的结构化信息。"""
    gpus: list[dict[str, Any]] = []
    expected_columns = len(_NVIDIA_QUERY_FIELDS)
    for row in csv.reader(output.splitlines()):
        if not row:
            continue
        if len(row) != expected_columns:
            raise ValueError(
                f"nvidia-smi 返回 {len(row)} 列，预期 {expected_columns} 列。"
            )
        gpu = {}
        for raw_value, (_, output_name, converter) in zip(
            row,
            _NVIDIA_QUERY_FIELDS,
        ):
            gpu[output_name] = _convert_nvidia_value(raw_value, converter)
        gpus.append(gpu)
    return gpus


def _get_selected_nvidia_devices() -> str | None:
    """读取进程选中的 NVIDIA 设备编号或 UUID，不允许隐式查询全部设备。"""
    value = os.getenv("CUDA_VISIBLE_DEVICES") or os.getenv(
        "NVIDIA_VISIBLE_DEVICES"
    )
    if value is None:
        return None

    value = value.strip()
    if not value or value.lower() in {"-1", "all", "none", "void"}:
        return None
    return value


def _collect_nvidia_info() -> dict[str, Any]:
    """使用 nvidia-smi 仅收集环境变量所选 GPU 的详细信息。"""
    selected_devices = _get_selected_nvidia_devices()
    if selected_devices is None:
        return {
            "available": False,
            "error": (
                "CUDA_VISIBLE_DEVICES or NVIDIA_VISIBLE_DEVICES does not select "
                "a specific GPU"
            ),
        }

    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {
            "available": False,
            "selected_devices": selected_devices,
            "error": "nvidia-smi is not installed or is not on PATH",
        }

    query = ",".join(field for field, _, _ in _NVIDIA_QUERY_FIELDS)
    result = _run_command(
        [
            executable,
            f"--id={selected_devices}",
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
        ]
    )
    if not result["ok"]:
        return {
            "available": False,
            "binary": executable,
            "selected_devices": selected_devices,
            "error": result["error"],
        }

    try:
        gpus = _parse_nvidia_csv(result["stdout"])
    except ValueError as exc:
        return {
            "available": False,
            "binary": executable,
            "selected_devices": selected_devices,
            "error": str(exc),
            "raw_output": result["stdout"],
        }

    process_result = _run_command(
        [
            executable,
            f"--id={selected_devices}",
            "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ]
    )
    processes: list[dict[str, Any]] = []
    if process_result["ok"] and process_result["stdout"]:
        for row in csv.reader(process_result["stdout"].splitlines()):
            if len(row) != 4:
                continue
            processes.append(
                {
                    "gpu_uuid": row[0].strip(),
                    "pid": _convert_nvidia_value(row[1], int),
                    "process_name": row[2].strip(),
                    "used_memory_mib": _convert_nvidia_value(row[3], int),
                }
            )

    info: dict[str, Any] = {
        "available": bool(gpus),
        "binary": executable,
        "selected_devices": selected_devices,
        "selected_gpu_count": len(gpus),
        "gpus": gpus,
        "compute_processes": processes,
    }
    if not process_result["ok"]:
        info["process_query_error"] = process_result["error"]
    return info


def _find_nvcc() -> str | None:
    """从 PATH 或 CUDA_HOME 中定位 nvcc。"""
    executable = shutil.which("nvcc")
    if executable:
        return executable
    cuda_home = os.getenv("CUDA_HOME")
    if cuda_home:
        candidate = Path(cuda_home).expanduser() / "bin" / "nvcc"
        if candidate.is_file():
            return str(candidate)
    return None


def _collect_cuda_toolkit_info() -> dict[str, Any]:
    """收集 CUDA Toolkit 路径和 nvcc 版本。"""
    executable = _find_nvcc()
    info: dict[str, Any] = {
        "cuda_home": os.getenv("CUDA_HOME"),
        "nvcc_available": executable is not None,
    }
    if executable is None:
        info["error"] = "nvcc was not found on PATH or under CUDA_HOME/bin"
        return info

    result = _run_command([executable, "--version"])
    info["nvcc_binary"] = executable
    if not result["ok"]:
        info["error"] = result["error"]
        return info

    output = result["stdout"]
    release_match = re.search(r"release\s+([\d.]+)", output)
    build_match = re.search(r"\bV([\d.]+)", output)
    info["cuda_release"] = release_match.group(1) if release_match else None
    info["build_version"] = build_match.group(1) if build_match else None
    info["raw_version"] = output
    return info


def _collect_torch_info() -> dict[str, Any]:
    """收集 PyTorch 构建信息、加速后端状态和可见 CUDA 设备属性。"""
    try:
        import torch
    except (ImportError, OSError) as exc:
        return {"available": False, "error": str(exc)}

    info: dict[str, Any] = {
        "available": True,
        "version": torch.__version__,
        "debug_build": bool(getattr(torch.version, "debug", False)),
        "compiled_cuda_version": getattr(torch.version, "cuda", None),
        "compiled_hip_version": getattr(torch.version, "hip", None),
    }
    try:
        info["cudnn_version"] = torch.backends.cudnn.version()
    except (AttributeError, RuntimeError):
        info["cudnn_version"] = None

    backends = {}
    captured_warnings: list[str] = []
    for backend_name in ("cuda", "npu", "mlu", "gcu", "xpu", "mps"):
        backend = getattr(torch, backend_name, None)
        is_available = getattr(backend, "is_available", None)
        if not callable(is_available):
            continue
        try:
            with warnings.catch_warnings(record=True) as warning_records:
                warnings.simplefilter("always")
                available = bool(is_available())
            captured_warnings.extend(str(item.message) for item in warning_records)
        except Exception as exc:  # 后端插件可能抛出非标准运行时异常。
            backends[backend_name] = {"available": False, "error": str(exc)}
            continue
        backends[backend_name] = {"available": available}
    info["backends"] = backends

    cuda_info = backends.setdefault("cuda", {"available": False})
    cuda_info["device_count"] = 0
    cuda_info["devices"] = []
    if cuda_info["available"]:
        try:
            cuda_info["device_count"] = torch.cuda.device_count()
            cuda_info["current_device"] = torch.cuda.current_device()
            cuda_info["architecture_list"] = torch.cuda.get_arch_list()
            for index in range(cuda_info["device_count"]):
                properties = torch.cuda.get_device_properties(index)
                device = {"index": index}
                for property_name in _TORCH_DEVICE_PROPERTIES:
                    value = getattr(properties, property_name, None)
                    if property_name == "total_memory" and isinstance(value, int):
                        device["total_memory_bytes"] = value
                    else:
                        device[property_name] = value
                cuda_info["devices"].append(device)
        except Exception as exc:
            cuda_info["error"] = str(exc)

    if captured_warnings:
        info["warnings"] = list(dict.fromkeys(captured_warnings))
    return info


def _read_first_matching_line(path: Path, prefix: str) -> str | None:
    """读取文本文件中第一个指定前缀的值。"""
    try:
        with path.open(encoding="utf-8", errors="replace") as file:
            for line in file:
                if line.startswith(prefix):
                    _, value = line.split(":", maxsplit=1)
                    return value.strip()
    except OSError:
        return None
    return None


def _collect_system_info() -> dict[str, Any]:
    """收集操作系统、CPU 和内存摘要。"""
    try:
        os_release = platform.freedesktop_os_release()
    except (AttributeError, OSError):
        os_release = {}

    memory_total_kib = _read_first_matching_line(
        Path("/proc/meminfo"),
        "MemTotal",
    )
    return {
        "hostname": socket.gethostname(),
        "operating_system": os_release.get("PRETTY_NAME") or platform.platform(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu_model": _read_first_matching_line(Path("/proc/cpuinfo"), "model name"),
        "logical_cpu_count": os.cpu_count(),
        "memory_total_kib": memory_total_kib,
    }


def collect_system_info() -> dict[str, Any]:
    """返回适合保存或交给 Agent 阅读的完整结构化环境信息。

    与原始实现相比，``python_executable`` 现在明确反映本脚本自身所在的解释器
    （即 ``.env`` 的 ``PYTHON_BIN``，也就是实际运行 benchmark 的解释器），确保
    agent 看到的 Python/PyTorch/CUDA 状态与 bench 环境完全一致。
    """
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "system": _collect_system_info(),
        "device_visibility": {
            key: os.getenv(key)
            for key in (
                "CUDA_VISIBLE_DEVICES",
                "NVIDIA_VISIBLE_DEVICES",
                "HIP_VISIBLE_DEVICES",
                "ROCR_VISIBLE_DEVICES",
                "MACA_VISIBLE_DEVICES",
                "TORCH_CUDA_ARCH_LIST",
            )
        },
        "interpreter": {
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "python_bin_env": os.getenv("PYTHON_BIN"),
        },
        "nvidia_smi": _collect_nvidia_info(),
        "cuda_toolkit": _collect_cuda_toolkit_info(),
        "pytorch": _collect_torch_info(),
    }


def _main() -> int:
    # Make the script independently runnable under $PYTHON_BIN. The wrapper
    # shell already exports .env, but this keeps direct invocation consistent.
    _load_dotenv_fallback(_ENV_FILE)

    # auto_choose_gpu() must run before torch is initialized so the selected
    # device is visible to both nvidia-smi and the torch.cuda.* queries below.
    # gpu_selector logs to stdout; we divert it to stderr so stdout stays a
    # single JSON payload that the langchain tool can parse untouched.
    sys.path.insert(0, str(_SCRIPT_DIR))
    real_stdout = sys.stdout
    try:
        sys.stdout = sys.stderr
        from gpu_selector import auto_choose_gpu

        auto_choose_gpu()
    except Exception as exc:
        os.environ["AUTO_CHOOSE_ERROR"] = str(exc)
    finally:
        sys.stdout = real_stdout

    info = collect_system_info()
    if "AUTO_CHOOSE_ERROR" in os.environ:
        info["auto_choose_error"] = os.environ.pop("AUTO_CHOOSE_ERROR")
    print(json.dumps(info, indent=2, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_main())