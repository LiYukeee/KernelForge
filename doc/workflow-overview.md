# 总体工作流

本章从使用者视角解释一次完整的优化循环是如何发生的。它不深入实现细节，而是把“接入算子、运行验证、记录结果、继续迭代”的主线串起来，帮助读者建立全局流程感。

## 一次完整循环

1. 选择一个待优化算子。
2. 把参考实现放入 `solution/model.py`。
3. 把待优化版本放入 `solution/model_new.py`。
4. 运行 `bash scripts/run.sh correctness` 验证功能正确。
5. 运行 `bash scripts/run.sh quick` 获取初步性能结果。
6. 运行 `bash scripts/run.sh full` 获取完整性能和 profiling 数据。
7. 使用 `/log-experiment` 归档本轮实验。
8. 根据结果继续下一轮优化，或放弃当前方向。

## 为什么先正确性后性能

- 模板默认把正确性放在第一优先级。
- 如果 `model_new.py` 输出不正确，后续性能结果没有参考价值。
- 这也是为什么 `run.py` 会先执行正确性测试，再进入性能测量。

## 三种运行模式

- `correctness`：只验证输出是否与基线一致。
- `quick`：验证正确性并进行较快的性能测量，适合日常迭代。
- `full`：验证正确性、进行更长时间的性能测量，并输出 profiling 结果，适合确认阶段与瓶颈分析。

## 手动迭代

- 手动修改 `solution/model_new.py`。
- 通过 `scripts/run.sh` 逐步验证结果。
- 使用 `/log-experiment` 记录一次实验的代码、日志和结论。

## 自动迭代

- 使用 `/optimize` 命令启动自主优化循环。
- 命令定义在 `.claude/commands/optimize.md` 中。
- 自动循环本质上还是围绕同一套 `correctness -> quick/full -> log-experiment` 的固定闭环展开。

## 子 Agent 在流程中的位置

- 当主循环不知道“时间到底花在哪”时，可调用 `profiler`，它读取 `scripts/output/profile_latest.txt` 并生成 `experiments/profile.md`。
- 当主循环不知道“下一个目标应该是谁”时，可调用 `workload-inspector`，它结合 `get_inputs()`、当前实现、profiling 热点和历史实验，生成 `experiments/workload_profile.md`。
- 当主循环出现平台期、重复试错或需要重新规划时，可调用 `research`，它从磁盘读取当前代码、实验历史和分析产物，生成下一轮 `plan.md`。
- 这三个 Agent 都不直接写优化内核，它们的作用是帮助主循环更快做出正确决策。

## 这套流程想解决什么问题

- 让不同算子的优化方式统一下来。
- 让每次实验都能被验证和回溯。
- 让“优化代码”和“评测代码”保持清晰分离。

## 延伸阅读

- [执行链路](execution-pipeline.md)
- [验证与评测体系](evaluation-and-benchmarking.md)
- [实验记录机制](experiment-management.md)
- [子 Agent 协作机制](sub-agents.md)
