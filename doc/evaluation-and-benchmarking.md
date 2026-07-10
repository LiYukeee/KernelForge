# 验证与评测体系

本章解释项目如何判断一次优化是否值得保留。模板不是只看“跑得快不快”，而是先看功能是否正确，再看延迟与加速比，最后在需要时通过 profiling 找出瓶颈位置。

## 为什么先正确性后性能

- 正确性是性能比较的前提。
- 如果 `model_new.py` 与 `model.py` 输出不一致，后续速度再快也没有意义。
- `scripts/run.py` 先调用正确性测试，只有通过之后才会继续进行性能测量。

## 三种运行模式

### `correctness`

- 只验证输出是否正确。
- 适合每次改完 `solution/model_new.py` 后快速做第一轮检查。

### `quick`

- 验证正确性并进行较短性能测试。
- 默认运行 100 次迭代，适合高频日常迭代。

### `full`

- 验证正确性并进行较长性能测试。
- 默认运行 1000 次迭代。
- 额外生成 `scripts/output/profile_latest.txt`，用于 profiling 分析。

## 正确性测试看什么

- 参考实现和优化实现都在 `torch.no_grad()` 下运行。
- 输出按块比较最大绝对误差。
- `run.py` 中默认正确性阈值为 `1e-4`。

## 性能测试看什么

- 会先执行 warmup，再进行正式计时。
- 最终关心的是平均每次迭代耗时。
- 日志中会输出基线耗时、优化版耗时和 `speedup(new/base)`。

## warmup 的作用

- 减少首次执行带来的额外抖动。
- 让正式计时更接近稳定状态下的真实耗时。
- 当前 `run.py` 默认 warmup 20 次。

## profiling 的作用

- `full` 模式会调用 `torch.profiler` 对 `model_new.py` 做分析。
- 结果按 `cuda_time_total` 排序输出前若干项。
- 这份结果更适合回答“时间花在哪”，而不是“整体快不快”。
- 当主循环需要把 profiling 结果进一步整理成“瓶颈结论 + 下一步 lever”时，可调用 `profiler` 子 Agent，它会把分析写入 `experiments/profile.md`。

## `torch.compile` 对比项

- `run.py` 中保留了 `COMPARE_TORCH_COMPILE` 开关。
- 打开后，会把 `torch.compile(model)` 作为额外参考对象。
- 它不是默认主路径，而是一个可选比较基线。

## 延伸阅读

- [执行链路](execution-pipeline.md)
- [实验记录机制](experiment-management.md)
- [总体工作流](workflow-overview.md)
- [子 Agent 协作机制](sub-agents.md)
