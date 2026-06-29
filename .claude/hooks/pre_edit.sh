#!/usr/bin/env bash
# PreToolUse hook for Edit / Write / NotebookEdit.
# Keeps the repo aligned with CLAUDE.md:
#   - solution/model.py is a read-only reference baseline
#   - solution/model_new.py is the optimization target
#   - scripts/ contains the fixed benchmark harness
set -eu

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

payload="$(cat)"
path="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
[ -z "$path" ] && exit 0

case "$path" in
  "$PROJECT_DIR"/*) rel="${path#$PROJECT_DIR/}" ;;
  /*)
    printf '[pre_edit.sh] Refusing to edit files outside the project: %s\n' "$path" >&2
    exit 2
    ;;
  *)
    rel="$path"
    ;;
esac

reject() {
  printf '[pre_edit.sh] %s\n' "$1" >&2
  exit 2
}

case "$rel" in
  solution/model.py)
    reject "solution/model.py is the reference implementation. Apply optimizations in solution/model_new.py instead."
    ;;
  solution/*)
    if [ "$rel" != "solution/model_new.py" ]; then
      reject "Only solution/model_new.py is writable under solution/. Refusing edit to '$rel'."
    fi
    ;;
  scripts/*)
    reject "scripts/ is the fixed benchmark harness for this task. Keep it unchanged and validate via 'bash scripts/run.sh <correctness|quick|full>'."
    ;;
esac

exit 0
