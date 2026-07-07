#!/usr/bin/env bash

export TORCH_CUDA_ARCH_LIST="12.0"
export CUDA_HOME=/usr/local/cuda-13.2
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
export PYTHON_BIN=/home/liyk/miniconda3/envs/llm/bin/python

# 默认不比较 torch.compile 版本；如需开启，改为 1
export COMPARE_TORCH_COMPILE=0
