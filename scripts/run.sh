#!/usr/bin/env bash
set -euo pipefail

# env setup
export TORCH_CUDA_ARCH_LIST="12.0"
export CUDA_HOME=/usr/local/cuda-13.2
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
PYTHON_BIN=/home/liyk/miniconda3/envs/llm/bin/python

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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/output"
LOG_FILE="$LOG_DIR/bench_latest.log"

mkdir -p "$LOG_DIR"
cd "$SCRIPT_DIR"
"$PYTHON_BIN" run.py --mode "$MODE" 2>&1 | tee "$LOG_FILE"
