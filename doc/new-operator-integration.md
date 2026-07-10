# 新算子接入方式

本章面向准备把新算子放进模板的读者。它解释如何从 `KernelBench` 选择一个算子，并把它接入到 `solution/` 的既定结构中，随后复用整个验证、评测和记录闭环。

## 接入目标

- 把一个新的参考实现放进 `solution/model.py`
- 把对应的优化版本放进 `solution/model_new.py`
- 保持模板已有脚本和流程不变

## 典型接入步骤

1. 从 `KernelBench` 选择一个目标算子。
2. 将参考实现整理为 `solution/model.py` 中的 `Model`。
3. 将待优化实现整理为 `solution/model_new.py` 中的 `Model`。
4. 根据该算子的输入需求实现 `get_inputs()`。
5. 如果模型初始化需要额外参数，实现 `get_init_inputs()`。
6. 通过 `bash scripts/run.sh correctness` 验证模板能正确运行。

## `model.py` 与 `model_new.py` 的分工

- `model.py` 是语义基线。
- `model_new.py` 是优化目标。
- 初次接入时，通常先让 `model_new.py` 与 `model.py` 保持一致，再逐步引入优化。

## `get_inputs()` 需要满足什么

- 返回 forward 所需的输入列表。
- 这些输入会在 `run.py` 中被搬到设备上。
- 输入应能代表该算子的典型 benchmark 场景。

## `get_init_inputs()` 需要满足什么

- 返回构造 `Model(...)` 时所需的初始化参数列表。
- 如果模型不需要特殊初始化参数，可以返回空列表。
- `run.py` 会用同样的初始化参数同时构造基线模型和优化模型。

## 接入后如何复用模板

- 运行 `bash scripts/run.sh correctness` 检查正确性。
- 运行 `bash scripts/run.sh quick` 获取初步性能数据。
- 必要时运行 `bash scripts/run.sh full` 获取 profiling 结果。
- 使用 `/log-experiment` 记录该算子的每一轮实验。

## 接入时最容易犯的错

- 把 `model.py` 当成也可以一起优化的文件。
- 绕过 `scripts/run.sh` 直接运行底层脚本。
- 没有保持 `get_inputs()` 与 `forward` 的接口对应关系。
- 修改了评测基础设施，导致结果难以比较。

## 延伸阅读

- [项目定位与适用场景](project-positioning.md)
- [总体工作流](workflow-overview.md)
- [执行链路](execution-pipeline.md)
