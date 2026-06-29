import sys
from pathlib import Path


def ensure_solution_dir_on_path(script_file: str | Path) -> Path:
    """Ensure the solution directory is importable when scripts run directly."""
    solution_dir = Path(script_file).resolve().parents[1] / "solution"
    solution_dir_str = str(solution_dir)

    if solution_dir_str not in sys.path:
        sys.path.insert(0, solution_dir_str)

    return solution_dir
