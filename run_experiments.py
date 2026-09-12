"""Run the GPU operator optimization workflow through a target round."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from langchain_core.callbacks import BaseCallbackHandler

from src.base.token_usage import TokenUsage, TokenUsageCallback
from src.code.agent import CodeAgent
from src.log.agent import LogAgent
from src.plan.agent import PlanAgent
from src.plan.utils import resolve_target_path


_ROUND_DIR_PATTERN = re.compile(r"round_(\d+)$")
_TOKEN_USAGE_FILENAME = "token_usage.jsonl"
_ResultT = TypeVar("_ResultT")


@dataclass(frozen=True)
class RoundResult:
    """Result of one fully archived optimization round."""

    round_number: int
    benchmark_succeeded: bool
    token_usage: TokenUsage = field(default_factory=TokenUsage)


class ExperimentStateError(RuntimeError):
    """Raised when existing experiment artifacts cannot be resumed safely."""


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run PLAN, CODE, and LOG agents through an absolute round number."
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Operator directory; relative paths are resolved from the current directory.",
    )
    parser.add_argument(
        "--rounds",
        required=True,
        type=_positive_int,
        metavar="N",
        help="Final absolute optimization round to complete.",
    )
    return parser


def _resolve_cli_target(raw_target: str) -> Path:
    if not raw_target.strip():
        raise ValueError("--target cannot be empty.")
    expanded = Path(os.path.expandvars(raw_target)).expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    return resolve_target_path(expanded.resolve())


def _nonempty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _round_directories(target_path: Path) -> list[tuple[int, Path]]:
    exp_dir = target_path / "exp"
    if not exp_dir.is_dir():
        return []

    rounds: list[tuple[int, Path]] = []
    for entry in exp_dir.iterdir():
        match = _ROUND_DIR_PATTERN.fullmatch(entry.name)
        if entry.is_dir() and match:
            round_number = int(match.group(1))
            if round_number <= 0:
                raise ExperimentStateError(
                    f"Invalid experiment round directory: {entry}"
                )
            rounds.append((round_number, entry))
    return sorted(rounds)


def _summary_round_counts(summary_path: Path) -> dict[int, int]:
    if not summary_path.is_file():
        return {}

    counts: dict[int, int] = {}
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip().strip("*").strip() for cell in stripped[1:-1].split("|")]
        if not cells or cells[0] == "round":
            continue
        try:
            round_number = int(cells[0])
        except ValueError:
            continue
        counts[round_number] = counts.get(round_number, 0) + 1
    return counts


def _round_is_complete(
    target_path: Path,
    round_number: int,
    summary_counts: dict[int, int] | None = None,
) -> bool:
    round_dir = target_path / "exp" / f"round_{round_number}"
    counts = (
        _summary_round_counts(target_path / "exp" / "summary.md")
        if summary_counts is None
        else summary_counts
    )
    return (
        _nonempty_file(round_dir / "plan.md")
        and _nonempty_file(round_dir / "model_new.py")
        and _nonempty_file(target_path / "exp" / "lessons.md")
        and counts.get(round_number) == 1
    )


def _starting_round(target_path: Path, final_round: int) -> int | None:
    rounds = _round_directories(target_path)
    if not rounds:
        if (target_path / "exp" / "summary.md").is_file():
            raise ExperimentStateError(
                "Experiment summary exists, but no round_N directories were found."
            )
        return 1

    numbers = [number for number, _ in rounds]
    expected = list(range(1, numbers[-1] + 1))
    if numbers != expected:
        raise ExperimentStateError(
            "Experiment round directories must be consecutive from round_1: "
            + ", ".join(f"round_{number}" for number in numbers)
        )

    summary_counts = _summary_round_counts(target_path / "exp" / "summary.md")
    for round_number, _ in rounds[:-1]:
        if not _round_is_complete(target_path, round_number, summary_counts):
            raise ExperimentStateError(
                f"Round {round_number} is incomplete but newer rounds exist; "
                "refusing to overwrite later experiment state."
            )

    latest_number, latest_dir = rounds[-1]
    latest_complete = _round_is_complete(target_path, latest_number, summary_counts)

    if latest_number > final_round:
        return None
    if latest_number == final_round and latest_complete:
        return None
    if latest_complete:
        return latest_number + 1

    plan_path = latest_dir / "plan.md"
    if plan_path.is_file() and not _nonempty_file(plan_path):
        raise ExperimentStateError(
            f"Round {latest_number} has an empty plan and cannot be resumed: {plan_path}"
        )
    return latest_number


def _run_stage(
    round_number: int,
    stage: str,
    operation: Callable[[], _ResultT],
) -> _ResultT:
    print(f"[round {round_number}] {stage} started", flush=True)
    try:
        result = operation()
    except Exception as exc:
        raise RuntimeError(
            f"Round {round_number} failed during {stage}: {exc}"
        ) from exc
    print(f"[round {round_number}] {stage} completed", flush=True)
    return result


def _token_usage_path(target_path: Path) -> Path:
    return target_path / "exp" / _TOKEN_USAGE_FILENAME


def _usage_from_record(record: dict[str, object]) -> TokenUsage:
    optional_fields = (
        "cache_hit_tokens",
        "cache_miss_tokens",
        "cache_creation_tokens",
        "reasoning_tokens",
    )
    models = record.get("models")
    return TokenUsage(
        llm_calls=int(record.get("llm_calls", 0)),
        usage_reported_calls=int(record.get("usage_reported_calls", 0)),
        input_tokens=int(record.get("input_tokens", 0)),
        output_tokens=int(record.get("output_tokens", 0)),
        total_tokens=int(record.get("total_tokens", 0)),
        **{
            name: int(value) if (value := record.get(name)) is not None else None
            for name in optional_fields
        },
        cache_hit_reported_calls=int(record.get("cache_hit_reported_calls", 0)),
        cache_miss_reported_calls=int(record.get("cache_miss_reported_calls", 0)),
        cache_creation_reported_calls=int(
            record.get("cache_creation_reported_calls", 0)
        ),
        reasoning_reported_calls=int(record.get("reasoning_reported_calls", 0)),
        models=tuple(
            str(model) for model in models if isinstance(model, str)
        )
        if isinstance(models, list)
        else (),
    )


def _read_token_usage_records(target_path: Path) -> list[dict[str, object]]:
    usage_path = _token_usage_path(target_path)
    if not usage_path.is_file():
        return []

    records: list[dict[str, object]] = []
    for line_number, line in enumerate(
        usage_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExperimentStateError(
                f"Invalid JSON in {usage_path} at line {line_number}."
            ) from exc
        if not isinstance(record, dict):
            raise ExperimentStateError(
                f"Token usage record at {usage_path}:{line_number} must be an object."
            )
        records.append(record)
    return records


def _append_token_usage_record(
    target_path: Path,
    round_number: int,
    stage: str,
    status: str,
    usage: TokenUsage,
) -> None:
    records = _read_token_usage_records(target_path)
    attempt = 1 + sum(
        record.get("round") == round_number and record.get("stage") == stage
        for record in records
    )
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "round": round_number,
        "stage": stage,
        "attempt": attempt,
        "status": status,
        **asdict(usage),
    }
    usage_path = _token_usage_path(target_path)
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    with usage_path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def _round_token_usage(target_path: Path, round_number: int) -> TokenUsage:
    return TokenUsage.combine(
        _usage_from_record(record)
        for record in _read_token_usage_records(target_path)
        if record.get("round") == round_number
    )


def _format_token_detail(
    value: int | None,
    reported_calls: int,
    llm_calls: int,
) -> str:
    if value is None:
        return "n/a"
    formatted = f"{value:,}"
    if reported_calls < llm_calls:
        return f"{formatted} (partial)"
    return formatted


def _format_core_tokens(value: int, usage: TokenUsage) -> str:
    if usage.usage_reported_calls == 0:
        return "n/a"
    formatted = f"{value:,}"
    if usage.usage_reported_calls < usage.llm_calls:
        return f"{formatted} (partial)"
    return formatted


def _print_token_usage(round_number: int, label: str, usage: TokenUsage) -> None:
    usage_coverage = f"{usage.usage_reported_calls}/{usage.llm_calls}"
    cache_hit = _format_token_detail(
        usage.cache_hit_tokens,
        usage.cache_hit_reported_calls,
        usage.llm_calls,
    )
    cache_miss = _format_token_detail(
        usage.cache_miss_tokens,
        usage.cache_miss_reported_calls,
        usage.llm_calls,
    )
    cache_creation = _format_token_detail(
        usage.cache_creation_tokens,
        usage.cache_creation_reported_calls,
        usage.llm_calls,
    )
    reasoning = _format_token_detail(
        usage.reasoning_tokens,
        usage.reasoning_reported_calls,
        usage.llm_calls,
    )
    print(
        f"[round {round_number}] {label} tokens: "
        f"calls={usage.llm_calls}, usage={usage_coverage}, "
        f"input={_format_core_tokens(usage.input_tokens, usage)}, "
        f"output={_format_core_tokens(usage.output_tokens, usage)}, "
        f"total={_format_core_tokens(usage.total_tokens, usage)}, "
        f"cache_hit={cache_hit}, cache_miss={cache_miss}, "
        f"cache_creation={cache_creation}, reasoning={reasoning}",
        flush=True,
    )


def _stage_config(
    callback: BaseCallbackHandler,
    round_number: int,
    stage: str,
) -> dict[str, object]:
    return {
        "callbacks": [callback],
        "tags": [f"round:{round_number}", f"stage:{stage.lower()}"],
        "metadata": {"round": round_number, "stage": stage.lower()},
    }


def _run_tracked_stage(
    target_path: Path,
    round_number: int,
    stage: str,
    operation: Callable[[dict[str, object]], _ResultT],
) -> tuple[_ResultT, TokenUsage]:
    print(f"[round {round_number}] {stage} started", flush=True)
    callback = TokenUsageCallback()
    try:
        result = operation(_stage_config(callback, round_number, stage))
    except Exception as exc:
        usage = callback.snapshot()
        _append_token_usage_record(
            target_path, round_number, stage, "failed", usage
        )
        _print_token_usage(round_number, stage, usage)
        raise RuntimeError(
            f"Round {round_number} failed during {stage}: {exc}"
        ) from exc

    usage = callback.snapshot()
    _append_token_usage_record(
        target_path, round_number, stage, "completed", usage
    )
    print(f"[round {round_number}] {stage} completed", flush=True)
    _print_token_usage(round_number, stage, usage)
    return result, usage


def _run_round(target_path: Path, round_number: int) -> RoundResult:
    plan_path = target_path / "exp" / f"round_{round_number}" / "plan.md"
    if _nonempty_file(plan_path):
        print(
            f"[round {round_number}] PLAN resumed from {plan_path}",
            flush=True,
        )
    else:
        plan_agent = _run_stage(
            round_number,
            "PLAN initialization",
            lambda: PlanAgent(target=target_path),
        )
        if plan_agent.round_number != round_number:
            raise ExperimentStateError(
                f"PLAN selected round {plan_agent.round_number}; expected {round_number}."
            )
        _run_tracked_stage(
            target_path,
            round_number,
            "PLAN",
            lambda config: plan_agent.run(config=config),
        )
        plan_path = plan_agent.plan_path
        if not _nonempty_file(plan_path):
            raise ExperimentStateError(
                f"PLAN did not create a non-empty plan: {plan_path}"
            )

    code_agent = _run_stage(
        round_number,
        "CODE initialization",
        lambda: CodeAgent(target=target_path, plan_path=plan_path),
    )
    code_result, _ = _run_tracked_stage(
        target_path,
        round_number,
        "CODE",
        lambda config: code_agent.run(config=config),
    )
    code_status = code_result.lstrip().splitlines()[0] if code_result.strip() else ""
    if code_status == "CODE_AGENT_SUCCEEDED":
        benchmark_succeeded = True
        print(f"[round {round_number}] benchmark succeeded", flush=True)
    elif code_status == "CODE_AGENT_FAILED":
        benchmark_succeeded = False
        print(
            f"[round {round_number}] benchmark failed; archiving and continuing",
            flush=True,
        )
    else:
        raise RuntimeError(
            f"Round {round_number} CODE returned an unknown status: "
            f"{code_status or '(empty result)'}"
        )

    log_agent = _run_stage(
        round_number,
        "LOG initialization",
        lambda: LogAgent(target=target_path, plan_path=plan_path),
    )
    _run_tracked_stage(
        target_path,
        round_number,
        "LOG",
        lambda config: log_agent.run(config=config),
    )
    if not _round_is_complete(target_path, round_number):
        raise ExperimentStateError(
            f"Round {round_number} finished without complete LOG artifacts."
        )
    round_usage = _round_token_usage(target_path, round_number)
    _print_token_usage(round_number, "ROUND TOTAL", round_usage)
    return RoundResult(round_number, benchmark_succeeded, round_usage)


def run_experiments(target_path: Path, final_round: int) -> list[RoundResult]:
    """Run or resume sequential optimization rounds through ``final_round``."""
    if final_round <= 0:
        raise ValueError("final_round must be a positive integer.")

    start_round = _starting_round(target_path, final_round)
    if start_round is None or start_round > final_round:
        print(
            f"Target already reached round {final_round}; no experiments to run.",
            flush=True,
        )
        return []

    results: list[RoundResult] = []
    for round_number in range(start_round, final_round + 1):
        results.append(_run_round(target_path, round_number))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        target_path = _resolve_cli_target(args.target)
        print(f"Target: {target_path}")
        print(f"Final round: {args.rounds}")
        results = run_experiments(target_path, args.rounds)
    except Exception as exc:
        print(f"Experiment failed: {exc}", file=sys.stderr)
        return 1

    succeeded = sum(result.benchmark_succeeded for result in results)
    failed = len(results) - succeeded
    print(
        f"Completed through round {args.rounds}. "
        f"Executed: {len(results)}; benchmark succeeded: {succeeded}; failed: {failed}."
    )
    print(f"Summary: {target_path / 'exp' / 'summary.md'}")
    usage_path = _token_usage_path(target_path)
    if usage_path.is_file():
        print(f"Token usage: {usage_path}")
    else:
        print("Token usage: no records (existing rounds predate token tracking).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
