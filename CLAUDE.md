# CLAUDE.md

由 `scripts/run.sh` 驱动的本地工作流的自主算子/模型优化系统。

## 优化任务

- **作为 CUDA 内核优化专家工作。** 将 `solution/model.py` 视为 PyTorch 参考实现，将 `solution/model_new.py` 作为唯一的优化目标。
- **仅优化推理路径。** 假设整个过程中使用 `model.eval()` 和 `torch.no_grad()` 语义；训练相关行为与推理正确性无关时不予考虑。
- **唯一允许的加速路径是使用 `torch.utils.cpp_extension.load_inline` 加载的手写 CUDA/C++ 或者 Triton 内核。** 通过逐步将 `solution/model_new.py` 中的 PyTorch 算子替换为显式自定义内核和调用所需的最小粘合代码来进行优化。
- **逐步替换 PyTorch 算子并持续验证。** 每次在 `solution/model_new.py` 中融合或重写一个部分，然后通过 `bash scripts/run.sh correctness` 验证，并使用 `bash scripts/run.sh quick` 或 `full` 测量性能。

## 工作流原则

- **只在 `solution/model_new.py` 中做优化。** `solution/model.py` 是基线参考和语义锚点，用来对照正确性与性能，不参与编辑。
- **每次迭代只做一个优化。** 小而可追溯的改动优于耦合编辑。
- **固定验证入口。** 使用 `bash scripts/run.sh correctness|quick|full` 进行正确性、性能和 profiling 验证；不要绕开 `scripts/run.sh` 直接运行底层脚本。
- **先关注绝对延迟，再看加速比。** 记录打印的 `Model`、`ModelNew` 和 `Model (compiled)` 平均延迟；仅将加速比作为摘要使用。
- **性能分析属于 `full` 模式。** `bash scripts/run.sh full` 将分析输出持久化到 `scripts/output/profile_latest.txt`。
- **保留最新日志产物。** `bash scripts/run.sh ...` 刷新 `scripts/output/bench_latest.log`；`/log-experiment` 对其进行快照。
- **通过 `/log-experiment` 记录每次实验**，包括失败的实验。
- **无快照，无实验。** 只有当实验文件夹同时包含 `result.md` 和复制的 `model_new.py` 时，该实验才被视为已记录。
- **跳过死胡同而非倒退。** 如果某个目标方向多次未能超越基线，标记为 `skip`，记录原因，然后转向下一个目标。
- **保持环境固定。** 不创建或切换虚拟环境，不安装、升级或卸载依赖项。

## 命令

| 命令 | 用途 |
|---|---|
| `/optimize` | 主循环 — 参见 `.claude/commands/optimize.md` |
| `/benchmark <correctness\|quick\|full>` | 运行本地基准测试/测试工作流 |
| `/log-experiment` | 快照 `model_new.py` + 最新日志/分析 + 写入 `result.md` |
