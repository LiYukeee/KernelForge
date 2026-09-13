"""Initialize KernelBench experiments under ``solution/L*/<task>/``.

Each source task is copied to both ``model.py`` (the immutable baseline) and
``model_new.py`` (the candidate that optimization rounds may edit).  Repeated
runs preserve existing candidates and reject baseline drift.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KERNELS_ROOT = PROJECT_ROOT.parent / "kernels"
DEFAULT_SOLUTION_ROOT = PROJECT_ROOT / "solution"
SUPPORTED_LEVELS = (1, 2, 3)
_TASK_FILENAME = re.compile(r"(?P<task_id>[1-9]\d*)_(?P<name>.+)\.py$")


class PreparationError(RuntimeError):
    """Raised when sources or existing experiment files are inconsistent."""


@dataclass(frozen=True)
class Experiment:
    """One source task and its destination experiment directory."""

    level: int
    task_id: int
    source: Path
    target_dir: Path


@dataclass(frozen=True)
class PreparationSummary:
    """Counts produced by a preparation or dry-run pass."""

    experiments: int
    directories_to_create: int
    baselines_to_create: int
    candidates_to_create: int
    baselines_unchanged: int
    candidates_preserved: int


def _resolve_path(raw_path: str | Path) -> Path:
    expanded = Path(os.path.expandvars(str(raw_path))).expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    return expanded.resolve()


def discover_experiments(
    kernels_root: Path,
    solution_root: Path,
    levels: Sequence[int],
) -> list[Experiment]:
    """Discover and validate numerically ordered KernelBench tasks."""
    experiments: list[Experiment] = []
    for level in sorted(set(levels)):
        if level not in SUPPORTED_LEVELS:
            raise PreparationError(f"Unsupported level: {level}")

        source_dir = kernels_root / f"level{level}"
        if not source_dir.is_dir():
            raise PreparationError(
                f"KernelBench level directory not found: {source_dir}"
            )

        level_experiments: list[Experiment] = []
        task_ids: list[int] = []
        for source in source_dir.iterdir():
            if not source.is_file() or source.suffix != ".py":
                continue
            match = _TASK_FILENAME.fullmatch(source.name)
            if match is None:
                raise PreparationError(f"Unexpected task filename: {source}")
            task_id = int(match.group("task_id"))
            task_ids.append(task_id)
            level_experiments.append(
                Experiment(
                    level=level,
                    task_id=task_id,
                    source=source,
                    target_dir=solution_root / f"L{level}" / source.stem,
                )
            )

        if not level_experiments:
            raise PreparationError(f"No Python tasks found in: {source_dir}")

        unique_ids = set(task_ids)
        duplicate_ids = sorted(
            task_id for task_id in unique_ids if task_ids.count(task_id) > 1
        )
        if duplicate_ids:
            rendered = ", ".join(map(str, duplicate_ids))
            raise PreparationError(
                f"Duplicate task IDs in {source_dir}: {rendered}"
            )

        expected_ids = set(range(1, max(unique_ids) + 1))
        missing_ids = sorted(expected_ids - unique_ids)
        if missing_ids:
            rendered = ", ".join(map(str, missing_ids))
            raise PreparationError(f"Missing task IDs in {source_dir}: {rendered}")

        experiments.extend(
            sorted(level_experiments, key=lambda experiment: experiment.task_id)
        )

    return experiments


def _preflight(experiments: Sequence[Experiment]) -> PreparationSummary:
    conflicts: list[str] = []
    directories_to_create = 0
    baselines_to_create = 0
    candidates_to_create = 0
    baselines_unchanged = 0
    candidates_preserved = 0

    for experiment in experiments:
        target_dir = experiment.target_dir
        if target_dir.exists() and not target_dir.is_dir():
            conflicts.append(f"experiment path is not a directory: {target_dir}")
            continue
        if not target_dir.exists():
            directories_to_create += 1

        source_bytes = experiment.source.read_bytes()
        baseline = target_dir / "model.py"
        candidate = target_dir / "model_new.py"

        if baseline.exists():
            if not baseline.is_file():
                conflicts.append(f"baseline path is not a file: {baseline}")
            elif baseline.read_bytes() != source_bytes:
                conflicts.append(
                    f"baseline differs from KernelBench source: {baseline}"
                )
            else:
                baselines_unchanged += 1
        else:
            baselines_to_create += 1

        if candidate.exists():
            if not candidate.is_file():
                conflicts.append(f"candidate path is not a file: {candidate}")
            else:
                candidates_preserved += 1
        else:
            candidates_to_create += 1

    if conflicts:
        details = "\n".join(f"- {conflict}" for conflict in conflicts)
        raise PreparationError(
            "Preparation aborted before writing because conflicts were found:\n"
            f"{details}"
        )

    return PreparationSummary(
        experiments=len(experiments),
        directories_to_create=directories_to_create,
        baselines_to_create=baselines_to_create,
        candidates_to_create=candidates_to_create,
        baselines_unchanged=baselines_unchanged,
        candidates_preserved=candidates_preserved,
    )


def prepare_experiments(
    experiments: Sequence[Experiment], *, dry_run: bool = False
) -> PreparationSummary:
    """Create missing files after validating the complete batch."""
    summary = _preflight(experiments)
    if dry_run:
        return summary

    for experiment in experiments:
        experiment.target_dir.mkdir(parents=True, exist_ok=True)
        source_bytes = experiment.source.read_bytes()
        for filename in ("model.py", "model_new.py"):
            destination = experiment.target_dir / filename
            if destination.exists():
                continue
            with destination.open("xb") as output:
                output.write(source_bytes)

    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create solution/L*/<task> experiment directories from KernelBench."
        )
    )
    parser.add_argument(
        "--kernels-root",
        default=DEFAULT_KERNELS_ROOT,
        help=f"KernelBench source root (default: {DEFAULT_KERNELS_ROOT})",
    )
    parser.add_argument(
        "--solution-root",
        default=DEFAULT_SOLUTION_ROOT,
        help=f"Experiment output root (default: {DEFAULT_SOLUTION_ROOT})",
    )
    parser.add_argument(
        "--levels",
        nargs="+",
        type=int,
        choices=SUPPORTED_LEVELS,
        default=SUPPORTED_LEVELS,
        metavar="LEVEL",
        help="Levels to prepare; defaults to 1 2 3.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report planned changes without writing files.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    kernels_root = _resolve_path(args.kernels_root)
    solution_root = _resolve_path(args.solution_root)
    try:
        experiments = discover_experiments(
            kernels_root, solution_root, args.levels
        )
        summary = prepare_experiments(experiments, dry_run=args.dry_run)
    except (OSError, PreparationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    level_counts = {
        level: sum(experiment.level == level for experiment in experiments)
        for level in sorted(set(args.levels))
    }
    mode = "Dry run" if args.dry_run else "Prepared"
    print(f"{mode} {summary.experiments} experiments: {level_counts}")
    print(
        "planned changes: "
        f"{summary.directories_to_create} directories, "
        f"{summary.baselines_to_create} model.py files, "
        f"{summary.candidates_to_create} model_new.py files"
    )
    print(
        "preserved existing files: "
        f"{summary.baselines_unchanged} baselines, "
        f"{summary.candidates_preserved} candidates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
