#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$(dirname "$SCRIPT_DIR")/.env"

if [[ ! -f "$ENV_FILE" ]]; then
	echo "Missing env file: $ENV_FILE" >&2
	exit 1
fi

# .env uses plain KEY=value lines (no `export`), so auto-export while sourcing.
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

# Resolve relative TARGET paths against the scripts directory so the
# workflow works from any working directory (e.g. the workspace root).
case "$TARGET" in
	/*) ;;
	*) TARGET="$SCRIPT_DIR/$TARGET" ;;
esac

# The benchmark always measures latency, so correctness mode uses one sample
# after accuracy validation rather than skipping its timing phase altogether.
MODE=full
MODE_SET=false
V0_FILE_ARG="${V0_FILE:-}"
V1_FILE_ARG="${V1_FILE:-}"

usage() {
	echo "Usage: scripts/bench.sh [full|quick|correctness] [V0_FILE] [V1_FILE]" >&2
	echo "       scripts/bench.sh [mode] [--v0-file PATH] [--v1-file PATH]" >&2
}

# The two file paths are optional. Positional paths are supported for concise
# local runs, while named options make CI invocations self-documenting.
POSITIONAL_FILES=()
while (($# > 0)); do
	case "$1" in
		full|quick|correctness)
			if [[ "$MODE_SET" == true || ${#POSITIONAL_FILES[@]} -gt 0 ]]; then
				echo "Mode must be the first positional argument and may only be specified once." >&2
				usage
				exit 2
			fi
			MODE="$1"
			MODE_SET=true
			shift
			;;
		--v0-file)
			if (($# < 2)); then
				echo "--v0-file requires a path." >&2
				usage
				exit 2
			fi
			V0_FILE_ARG="$2"
			shift 2
			;;
		--v1-file)
			if (($# < 2)); then
				echo "--v1-file requires a path." >&2
				usage
				exit 2
			fi
			V1_FILE_ARG="$2"
			shift 2
			;;
		-h|--help)
			usage
			exit 0
			;;
		-*)
			echo "Unknown option: $1" >&2
			usage
			exit 2
			;;
		*)
			POSITIONAL_FILES+=("$1")
			shift
			;;
	esac
done

if ((${#POSITIONAL_FILES[@]} > 2)); then
	echo "At most V0_FILE and V1_FILE may be provided as positional arguments." >&2
	usage
	exit 2
fi

if ((${#POSITIONAL_FILES[@]} >= 1)); then
	if [[ -n "$V0_FILE_ARG" ]]; then
		echo "V0_FILE was provided both positionally and with --v0-file." >&2
		usage
		exit 2
	fi
	V0_FILE_ARG="${POSITIONAL_FILES[0]}"
fi
if ((${#POSITIONAL_FILES[@]} == 2)); then
	if [[ -n "$V1_FILE_ARG" ]]; then
		echo "V1_FILE was provided both positionally and with --v1-file." >&2
		usage
		exit 2
	fi
	V1_FILE_ARG="${POSITIONAL_FILES[1]}"
fi

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
		usage
		exit 2
		;;
esac

# Allow external harnesses to provide TARGET, while local runs benchmark the
# solution files shipped with this workspace.
LOG_DIR="$TARGET/bench_output"
LOG_FILE="$LOG_DIR/bench_latest.log"
V0_FILE="${V0_FILE_ARG:-$TARGET/model.py}"
V1_FILE="${V1_FILE_ARG:-$TARGET/model_new.py}"

# Resolve custom file paths from the caller's working directory. Defaults
# remain relative to TARGET, preserving the original behavior.
if [[ "$V0_FILE" != /* ]]; then
	V0_FILE="$(pwd -P)/$V0_FILE"
fi
if [[ "$V1_FILE" != /* ]]; then
	V1_FILE="$(pwd -P)/$V1_FILE"
fi

if [[ ! -f "$V0_FILE" || ! -f "$V1_FILE" ]]; then
	echo "Expected model files were not found under TARGET=$TARGET" >&2
	exit 1
fi

mkdir -p "$LOG_DIR"

cd "$SCRIPT_DIR"
export PYTHONPATH="$TARGET${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON_BIN" bench.py \
	--v0_file "$V0_FILE" \
	--v1_file "$V1_FILE" \
	--warmup "$WARMUP" \
	--repeat "$REPEAT" \
	2>&1 | tee "$LOG_FILE"
