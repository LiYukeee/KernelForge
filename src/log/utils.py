"""LOG Agent 的 benchmark 解析辅助函数。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_PASS_PATTERN = re.compile(
    rf"^PASS accuracy;\s*v0={_NUMBER}\s+ms,\s*"
    rf"v1=(?P<latency>{_NUMBER})\s+ms,\s*"
    rf"speedup=(?P<speedup>{_NUMBER}|inf)x\s*$",
    re.MULTILINE,
)
_FAILURE_PATTERN = re.compile(
    r"^(?:FAIL(?:\s|$)|Summary:\s*0 passed,\s*1 failed,\s*1 total\.)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class BenchmarkRecord:
    """一轮 benchmark 写入汇总表的固定字段。"""

    model_new_latency: str
    speedup: str
    correctness: str


def parse_benchmark_log(log_path: Path) -> BenchmarkRecord:
    """从 benchmark 原始日志提取 V1 指标；失败时不虚构性能数据。"""
    if not log_path.is_file():
        raise FileNotFoundError(f"LOG Agent 找不到 benchmark 日志：{log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    matches = list(_PASS_PATTERN.finditer(log_text))
    if matches:
        latest = matches[-1]
        return BenchmarkRecord(
            model_new_latency=f"{latest.group('latency')} ms",
            speedup=f"{latest.group('speedup')}x",
            correctness="通过",
        )
    if _FAILURE_PATTERN.search(log_text):
        return BenchmarkRecord(
            model_new_latency="N/A",
            speedup="N/A",
            correctness="失败",
        )
    raise RuntimeError(f"LOG Agent 无法从 benchmark 日志判断实验结果：{log_path}")
