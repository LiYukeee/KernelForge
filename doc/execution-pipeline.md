# 执行链路

本章解释一次 benchmark 命令从哪里进入、依次经过哪些脚本、最终生成哪些结果文件。读完之后，读者应该能清楚知道为什么项目要求统一走 `scripts/run.sh`，以及日志与 profiling 数据是如何产出的。

## 为什么统一从 `scripts/run.sh` 进入

- `scripts/run.sh` 是项目规定的唯一 benchmark 入口。
- 它先加载 `scripts/env.sh`，确保平台相关环境变量和 Python 路径被正确设置。
- 它再调用 `scripts/run.py`，并把输出写入 `scripts/output/bench_latest.log`。
- 统一入口的目的是固定环境、固定参数和固定日志位置。

## 调用顺序

核心调用链如下：

`scripts/run.sh -> scripts/env.sh -> scripts/run.py -> scripts/src/benchmark.py`

在这个过程中，还会间接使用：

- `scripts/src/gpu_selector.py`
- `scripts/src/compile_guard.py`
- `scripts/src/path_bootstrap.py`

## `env.sh` 负责什么

- 判断当前平台是 NVIDIA 还是 Metax。
- 设置如 `CUDA_HOME`、`MACA_HOME`、`PYTHON_BIN` 等运行变量。
- 设置 `COMPARE_TORCH_COMPILE` 这类测试开关。

## `run.py` 负责什么

- 调用 GPU 自动选择逻辑。
- 把 `solution/` 加入导入路径。
- 导入 `model.py` 和 `model_new.py`。
- 用编译保护机制加载 `model_new.py`。
- 构造输入、实例化模型、同步权重。
- 先测正确性，再测性能，最后在 `full` 模式下做 profiling。

## GPU 自动选择

- `scripts/src/gpu_selector.py` 会尝试根据平台工具选择空闲设备。
- NVIDIA 分支依赖 `nvidia-smi`。
- Metax 分支依赖 `mx-smi`。
- 这样做的目的是在多卡环境下尽量自动选择更空闲的设备。

## 模型加载与同步

- `model.py` 提供参考实现。
- `model_new.py` 提供优化实现。
- `run.py` 会用相同初始化参数构造两者。
- 如果结构一致，会通过 `load_state_dict` 同步权重，以便公平比较输出和性能。

## 输出产物

- `scripts/output/bench_latest.log`：最近一次 benchmark 日志。
- `scripts/output/profile_latest.txt`：最近一次 `full` 模式 profiling 结果。
- 这两个文件也是后续 `/log-experiment` 归档的重要输入。

## 延伸阅读

- [环境与平台重点](environment-and-platform.md)
- [验证与评测体系](evaluation-and-benchmarking.md)
- [总体工作流](workflow-overview.md)
