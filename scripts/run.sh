#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/env.sh"

# 在脚本最开始加载环境变量，确保后续参数解析和命令执行都使用统一环境。
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

# env.sh 负责集中维护运行所需的环境变量，例如 CUDA 和 Python 路径。
# shellcheck source=/dev/null
source "$ENV_FILE"

# 支持参数: full(默认,1000iter+profiling) / quick(100iter,无profiling) / correctness(仅正确性)
# full 模式会将 profiling 结果持久化到 output/profile_latest.txt
MODE=${1:-full}
case "$MODE" in
  full|quick|correctness)
    ;;
  *)
    echo "Unsupported mode: $MODE" >&2
    echo "Usage: scripts/run.sh [full|quick|correctness]" >&2
    exit 2
    ;;
esac

LOG_DIR="$SCRIPT_DIR/output"
LOG_FILE="$LOG_DIR/bench_latest.log"

mkdir -p "$LOG_DIR"
cd "$SCRIPT_DIR"
"$PYTHON_BIN" run.py --mode "$MODE" 2>&1 | tee "$LOG_FILE"
