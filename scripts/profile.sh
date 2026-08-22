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

# Resolve relative TARGET paths against the scripts directory so the workflow
# works from any working directory (e.g. the workspace root).
case "$TARGET" in
	/*) ;;
	*) TARGET="$SCRIPT_DIR/$TARGET" ;;
esac

V1_FILE_ARG="${V1_FILE:-}"
WARMUP="${PROFILE_WARMUP:-200}"
ITERATIONS="${PROFILE_ITERATIONS:-10}"

usage() {
	echo "Usage: scripts/profile.sh [V1_FILE]" >&2
	echo "       scripts/profile.sh [--v1-file PATH] [--warmup N] [--iterations N]" >&2
}

POSITIONAL_FILES=()
while (($# > 0)); do
	case "$1" in
		--v1-file)
			if (($# < 2)); then
				echo "--v1-file requires a path." >&2
				usage
				exit 2
			fi
			V1_FILE_ARG="$2"
			shift 2
			;;
		--warmup)
			if (($# < 2)); then
				echo "--warmup requires a non-negative integer." >&2
				usage
				exit 2
			fi
			WARMUP="$2"
			shift 2
			;;
		--iterations)
			if (($# < 2)); then
				echo "--iterations requires a positive integer." >&2
				usage
				exit 2
			fi
			ITERATIONS="$2"
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

if ((${#POSITIONAL_FILES[@]} > 1)); then
	echo "Only V1_FILE may be provided as a positional argument." >&2
	usage
	exit 2
fi

if ((${#POSITIONAL_FILES[@]} == 1)); then
	if [[ -n "$V1_FILE_ARG" ]]; then
		echo "V1_FILE was provided both positionally and with --v1-file." >&2
		usage
		exit 2
	fi
	V1_FILE_ARG="${POSITIONAL_FILES[0]}"
fi

if ! [[ "$WARMUP" =~ ^[0-9][0-9]*$ ]]; then
	echo "PROFILE_WARMUP/--warmup must be a non-negative integer: $WARMUP" >&2
	exit 2
fi
if ! [[ "$ITERATIONS" =~ ^[1-9][0-9]*$ ]]; then
	echo "PROFILE_ITERATIONS/--iterations must be a positive integer: $ITERATIONS" >&2
	exit 2
fi

LOG_DIR="$TARGET/bench_output"
PROFILE_FILE="$LOG_DIR/torch_profile_latest.txt"
V1_FILE="${V1_FILE_ARG:-$TARGET/model_new.py}"

# Resolve custom file paths from the caller's working directory. The default
# remains relative to TARGET, matching bench.sh.
if [[ "$V1_FILE" != /* ]]; then
	V1_FILE="$(pwd -P)/$V1_FILE"
fi

if [[ ! -f "$V1_FILE" ]]; then
	echo "V1 model file was not found: $V1_FILE" >&2
	exit 1
fi

mkdir -p "$LOG_DIR"

cd "$SCRIPT_DIR"
export PYTHONPATH="$TARGET${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON_BIN" profile.py \
	--v1_file "$V1_FILE" \
	--profile-output "$PROFILE_FILE" \
	--warmup "$WARMUP" \
	--iterations "$ITERATIONS"
