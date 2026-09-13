#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RUNNER="$PROJECT_ROOT/run_experiments.py"

usage() {
	cat <<'EOF'
Usage: scripts/run_experiments_parallel.sh DIRECTORY [ROUNDS] [N_JOBS] [DELAY_TIME]

Run every experiment directly under DIRECTORY through the requested round.

Arguments:
  DIRECTORY   Parent directory containing experiment directories
  ROUNDS      Final round passed to run_experiments.py (default: 10)
  N_JOBS      Maximum concurrent experiments (default: $N_JOBS or 4)
  DELAY_TIME  Delay between job starts in seconds (default: $DELAY_TIME or 0)

Environment:
  RUN_EXPERIMENTS_PYTHON  Python interpreter used to start the runner
                          (default: python from the current shell environment)
EOF
}

if (($# == 1)) && [[ "$1" == "-h" || "$1" == "--help" ]]; then
	usage
	exit 0
fi

if (($# < 1 || $# > 4)); then
	usage >&2
	exit 2
fi

experiment_root="$1"
rounds="${2:-10}"
n_jobs="${3:-${N_JOBS:-4}}"
delay_time="${4:-${DELAY_TIME:-20}}"
python_command="${RUN_EXPERIMENTS_PYTHON:-python}"

if [[ ! -d "$experiment_root" ]]; then
	echo "Experiment directory does not exist: $experiment_root" >&2
	exit 1
fi
experiment_root="$(cd "$experiment_root" && pwd -P)"

if ! [[ "$rounds" =~ ^[1-9][0-9]*$ ]]; then
	echo "ROUNDS must be a positive integer: $rounds" >&2
	exit 2
fi
if ! [[ "$n_jobs" =~ ^[1-9][0-9]*$ ]]; then
	echo "N_JOBS must be a positive integer: $n_jobs" >&2
	exit 2
fi
if ! [[ "$delay_time" =~ ^([0-9]+([.][0-9]*)?|[.][0-9]+)$ ]]; then
	echo "DELAY_TIME must be a non-negative number: $delay_time" >&2
	exit 2
fi
if [[ ! -f "$RUNNER" ]]; then
	echo "Runner does not exist: $RUNNER" >&2
	exit 1
fi
if ! command -v parallel >/dev/null 2>&1; then
	echo "GNU parallel is required but was not found in PATH." >&2
	exit 1
fi
if ! python_bin="$(command -v "$python_command")"; then
	echo "Python interpreter was not found in PATH: $python_command" >&2
	exit 1
fi

command_list=()
while IFS= read -r -d '' experiment_dir; do
	if [[ ! -f "$experiment_dir/model.py" || ! -f "$experiment_dir/model_new.py" ]]; then
		echo "Skipping non-experiment directory: $experiment_dir" >&2
		continue
	fi

	printf -v command '%q %q --target %q --rounds %q' \
		"$python_bin" "$RUNNER" "$experiment_dir" "$rounds"
	command_list+=("$command")
done < <(find "$experiment_root" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

if ((${#command_list[@]} == 0)); then
	echo "No experiments containing model.py and model_new.py were found under: $experiment_root" >&2
	exit 1
fi

echo "Queued ${#command_list[@]} experiments from $experiment_root"
echo "Final round: $rounds; parallel jobs: $n_jobs; start delay: ${delay_time}s"
parallel --jobs "$n_jobs" --delay "$delay_time" ::: "${command_list[@]}"
