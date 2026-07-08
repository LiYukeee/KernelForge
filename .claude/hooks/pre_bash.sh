#!/usr/bin/env bash
# PreToolUse hook for Bash. Rejects policy violations and nudges commands
# toward the local optimization workflow described in CLAUDE.md.
set -eu

payload="$(cat)"
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')"
[ -z "$cmd" ] && exit 0

reject() {
  printf '[pre_bash.sh] %s\n' "$1" >&2
  exit 2
}

# Defense in depth for destructive operations.
case "$cmd" in
  *"git reset --hard"*)
    reject "'git reset --hard' is denied. Revert specific changes instead."
    ;;
  *"git push --force"*|*"git push -f "*|*"git push -f"|*" -f "*"git push"*)
    reject "'git push --force' is denied. Resolve the divergence instead."
    ;;
  *"rm -rf solution"*|*"rm -rf ./solution"*|*"rm -rf /home/liyk/code/kernel-proj/KernelForge/solution"*)
    reject "'rm -rf solution' is denied. Delete individual files only when the user explicitly asks."
    ;;
  *"rm -rf scripts"*|*"rm -rf ./scripts"*|*"rm -rf /home/liyk/code/kernel-proj/KernelForge/scripts"*)
    reject "'rm -rf scripts' is denied."
    ;;
esac

# Keep benchmark entrypoints consistent with scripts/run.sh so CUDA env setup
# and artifact logging always happen the same way.
if printf '%s' "$cmd" | grep -qE '(^|[[:space:]])(python|python3)[[:space:]]+scripts/run\.py([[:space:]]|$)'; then
  reject "Run benchmarks through 'bash scripts/run.sh <correctness|quick|full>' so the pinned CUDA environment and logs stay consistent."
fi

if printf '%s' "$cmd" | grep -qE '(^|[[:space:]])(\./)?scripts/run\.sh([[:space:]]|$)'; then
  if ! printf '%s' "$cmd" | grep -qE '(^|[[:space:]])(\./)?scripts/run\.sh([[:space:]]+(full|quick|correctness))?([[:space:]]|$)'; then
    reject "scripts/run.sh only accepts: correctness, quick, or full."
  fi
fi

exit 0
