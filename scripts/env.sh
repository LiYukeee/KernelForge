#!/usr/bin/env bash

if command -v nvidia-smi >/dev/null 2>&1; then
  export TORCH_CUDA_ARCH_LIST="12.0"
  export CUDA_HOME=/usr/local/cuda-13.2
  export PATH="$CUDA_HOME/bin:$PATH"
  export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
  export PYTHON_BIN=/home/liyk/miniconda3/envs/llm/bin/python
elif command -v mx-smi >/dev/null 2>&1; then
  export MACA_HOME=/opt/maca-3.3.0
  export PYTHON_BIN=/home/yuke/miniforge-pypy3/envs/mxtorch/bin/python
else
  echo "Neither nvidia-smi nor mx-smi was found in PATH." >&2
  return 1 2>/dev/null || exit 1
fi

# 默认不比较 torch.compile 版本；如需开启，改为 1
export COMPARE_TORCH_COMPILE=0
