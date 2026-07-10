# 环境与平台重点

本章解释项目依赖什么运行环境，以及为什么文档叙述会以 Metax 为重点。读者不需要在这里学习所有底层平台知识，但应明确项目如何区分 NVIDIA 与 Metax，以及环境稳定性为什么是模板成立的前提。

## 运行前提

- Python 3.10+
- 对应平台可用的 PyTorch 环境
- GPU 平台工具可用
- `scripts/env.sh` 中定义的运行路径和环境变量正确

## 两条平台分支

项目在 `scripts/env.sh` 和 `scripts/src/gpu_selector.py` 中显式区分两类平台：

- NVIDIA：依赖 `nvidia-smi`
- Metax：依赖 `mx-smi`

## NVIDIA 分支

- `scripts/env.sh` 会设置 `CUDA_HOME`、`TORCH_CUDA_ARCH_LIST`、`LD_LIBRARY_PATH` 等变量。
- `gpu_selector.py` 会通过 `nvidia-smi` 查询显存占用，并自动选择更空闲的设备。
- 这一分支用于兼容常见 CUDA 环境。

## Metax 分支

- `scripts/env.sh` 会设置 `MACA_HOME` 与对应的 `PYTHON_BIN`。
- `gpu_selector.py` 会通过 `mx-smi --show-memory` 解析设备显存使用情况，并设置 `MACA_VISIBLE_DEVICES`。
- 当前项目虽然支持双平台，但更强调 Metax 侧的工作方式与环境理解。

## 为什么文档以 Metax 为主线

- 这是当前项目的实际侧重点。
- 对读者来说，理解 Metax 路径比平均介绍两边更有价值。
- NVIDIA 相关内容仍然保留，但主要用于说明兼容性而不是主叙事。

## 为什么环境稳定很重要

- benchmark 结果依赖平台、驱动、Python 环境和工具链。
- 如果环境在实验过程中频繁变化，性能对比就会失真。
- 这也是为什么项目禁止随意安装、升级和拉取外部依赖。

## 读者应关注什么

- 当前机器实际走的是哪条平台分支。
- `scripts/env.sh` 中的路径和解释器配置是否匹配当前环境。
- benchmark 结果是否与当前平台一致理解，而不是混淆了 NVIDIA 与 Metax 的上下文。

## 延伸阅读

- [执行链路](execution-pipeline.md)
- [项目定位与适用场景](project-positioning.md)
- [权限模型](permission-model.md)
