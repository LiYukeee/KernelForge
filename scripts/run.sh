#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/env.sh"

if [[ ! -f "$ENV_FILE" ]]; then
	echo "Missing env file: $ENV_FILE" >&2
	exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

# Resolve relative TARGET paths against the scripts directory so the
# workflow works from any working directory (e.g. the workspace root).
case "$TARGET" in
	/*) ;;
	*) TARGET="$SCRIPT_DIR/$TARGET" ;;
esac

# Keep the interface consistent with run.sh. new_bench.py always measures
# latency, so correctness mode uses one untimed-style sample after accuracy
# validation rather than skipping its required timing phase altogether.
MODE=${1:-full}
case "$MODE" in
	full)
		WARMUP=200
		REPEAT=500
		;;
	quick)
		WARMUP=20
		REPEAT=100
		;;
	correctness)
		WARMUP=0
		REPEAT=1
		;;
	*)
		echo "Unsupported mode: $MODE" >&2
		echo "Usage: scripts/run_new.sh [full|quick|correctness]" >&2
		exit 2
		;;
esac

# Allow external harnesses to provide TARGET, while local runs benchmark the
# solution files shipped with this workspace.
LOG_DIR="$TARGET/bench_output"
LOG_FILE="$LOG_DIR/bench_latest.log"
PROFILE_FILE="$LOG_DIR/profile_latest.txt"
V0_FILE="$TARGET/model.py"
V1_FILE="$TARGET/model_new.py"

if [[ ! -f "$V0_FILE" || ! -f "$V1_FILE" ]]; then
	echo "Expected model files were not found under TARGET=$TARGET" >&2
	exit 1
fi

rm -rf "$LOG_DIR"
mkdir -p "$LOG_DIR"

cd "$SCRIPT_DIR"
export PYTHONPATH="$TARGET${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON_BIN" bench.py \
	--v0_file "$V0_FILE" \
	--v1_file "$V1_FILE" \
	--warmup "$WARMUP" \
	--repeat "$REPEAT" \
	2>&1 | tee "$LOG_FILE"

if [[ "$MODE" == "full" ]]; then
	"$PYTHON_BIN" profile_model_new.py \
		--v0_file "$V0_FILE" \
		--v1_file "$V1_FILE" \
		--profile-output "$PROFILE_FILE"
fi
