#!/usr/bin/env bash
# Stop hook: non-blocking reminders tied to the local optimization loop.
# Always exits 0 so the session can close cleanly.
set -eu

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MODEL_FILE="$PROJECT_DIR/solution/model_new.py"
LOG_FILE="$PROJECT_DIR/scripts/output/bench_latest.log"
PROFILE_FILE="$PROJECT_DIR/scripts/output/profile_latest.txt"

warn() {
  printf '[stop.sh] %s\n' "$1" >&2
}

if [ -f "$MODEL_FILE" ]; then
  if [ ! -f "$LOG_FILE" ]; then
    warn "No scripts/output/bench_latest.log found. Run 'bash scripts/run.sh correctness' after editing solution/model_new.py."
  elif [ "$MODEL_FILE" -nt "$LOG_FILE" ]; then
    warn "solution/model_new.py is newer than scripts/output/bench_latest.log. Re-run 'bash scripts/run.sh correctness' or 'quick' before stopping."
  fi

  if [ ! -f "$PROFILE_FILE" ]; then
    warn "No scripts/output/profile_latest.txt found. Run 'bash scripts/run.sh full' when you need fresh profiling data."
  elif [ "$MODEL_FILE" -nt "$PROFILE_FILE" ]; then
    warn "solution/model_new.py is newer than scripts/output/profile_latest.txt. Run 'bash scripts/run.sh full' before drawing profiling conclusions."
  fi
fi

exit 0
