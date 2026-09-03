#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$(dirname "$SCRIPT_DIR")/.env"

if [[ ! -f "$ENV_FILE" ]]; then
	echo "Missing env file: $ENV_FILE" >&2
	exit 1
fi

# .env mixes plain KEY=value and `export KEY=value` lines; sourcing under
# `set -a` auto-exports the plain ones and honors the `export`ed ones alike.
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

if [[ -z "${PYTHON_BIN:-}" ]]; then
	echo "PYTHON_BIN is not set in $ENV_FILE" >&2
	exit 1
fi

# Run the collector in the benchmark interpreter (torch_new) so Python,
# PyTorch, and accelerator state match the environment that actually runs
# scripts/bench.py. PYTHONPATH is set so the collector can find scripts/.
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON_BIN" get_system_info.py "$@"