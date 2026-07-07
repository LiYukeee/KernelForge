#!/usr/bin/env bash

export MACA_HOME=/opt/maca-3.3.0
export PYTHON_BIN=/home/yuke/miniforge-pypy3/envs/mxtorch/bin/python
# 默认不比较 torch.compile 版本；如需开启，改为 1
export COMPARE_TORCH_COMPILE=0