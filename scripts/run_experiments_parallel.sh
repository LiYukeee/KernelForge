#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RUNNER="$PROJECT_ROOT/run_experiments.py"

# Edit these values directly before running the script.
experiment_root="$PROJECT_ROOT/solution/L3"
rounds=10
n_jobs=1
delay_time=20
python_command="python"
log_filename="run_experiments.log"

command_list=()
experiment_list=()
while IFS= read -r -d '' experiment_dir; do
	if [[ ! -f "$experiment_dir/model.py" || ! -f "$experiment_dir/model_new.py" ]]; then
		echo "Skipping non-experiment directory: $experiment_dir" >&2
		continue
	fi

	mkdir -p "$experiment_dir/log"
	log_file="$experiment_dir/log/$log_filename"
	# Use unbuffered Python and redirect both streams so each experiment has its own live log.
	printf -v command '%q -u %q --target %q --rounds %q > %q 2>&1' \
		"$python_command" "$RUNNER" "$experiment_dir" "$rounds" "$log_file"
	command_list+=("$command")
	experiment_list+=("$experiment_dir")
done < <(find "$experiment_root" -mindepth 1 -maxdepth 1 -type d -print0 | sort -V -z)

if ((${#command_list[@]} == 0)); then
	echo "No experiments containing model.py and model_new.py were found under: $experiment_root" >&2
	exit 1
fi

echo "Queued ${#command_list[@]} experiments from $experiment_root"
echo "Final round: $rounds; parallel jobs: $n_jobs; start delay: ${delay_time}s"
for index in "${!experiment_list[@]}"; do
	printf '[job %d] %s -> %s\n' \
		"$((index + 1))" \
		"${experiment_list[$index]}" \
		"${experiment_list[$index]}/log/$log_filename"
done

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
parallel \
	--jobs "$n_jobs" \
	--delay "$delay_time" \
	--line-buffer \
	--tagstring '[job {#}]' \
	::: "${command_list[@]}"
