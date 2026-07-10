# 子 Agent 协作机制

本章专门解释 `.claude/agents/` 里的 3 个子 Agent 在优化循环中分别做什么。它们不是额外的装饰能力，而是帮助主循环完成“测量瓶颈、选择目标、规划实验”这三类高判断成本任务的协作角色。

## 为什么要有子 Agent

- 算子优化不只是写代码，还包含大量判断工作。
- 主循环经常需要回答三个问题：时间花在哪、下一步该优化谁、下一轮实验怎么安排。
- 这三个问题分别由 `profiler`、`workload-inspector`、`research` 负责，会比把所有诊断逻辑混在一起更清晰。

## 三个 Agent 的总分工

- `profiler`：回答“当前最大的瓶颈是什么”。
- `workload-inspector`：回答“基于输入与热点，下一步最值得优化的目标是谁”。
- `research`：回答“结合历史实验和当前状态，下一轮实验计划应该怎么写”。

## `profiler`

### 核心作用

- 读取最新的 profiling 产物。
- 把底层热点整理成高层阶段结论。
- 指出当前最大的瓶颈，以及最具体的下一个优化 lever。

### 主要输入

- `scripts/output/profile_latest.txt`
- `solution/model_new.py`
- `scripts/run.py`
- `scripts/src/benchmark.py`
- 已存在的实验总结和 lessons

### 主要输出

- `experiments/profile.md`

### 适合什么时候调用

- 已经有 `full` 模式 profiling 结果，但不知道真正的瓶颈在哪。
- 准备重写某一段实现之前，想先确认它确实是主要耗时。
- 需要把原始 profiler 表格整理成可读结论时。

## `workload-inspector`

### 核心作用

- 检查 `get_inputs()` 返回的真实工作负载。
- 结合输入形状、dtype、layout、内存足迹、profiling 热点和历史实验，判断“下一个最值得优化的目标”。
- 在“继续重试当前目标”与“切换到其他目标”之间做推荐。

### 主要输入

- `solution/model.py` 中的 `get_inputs()`
- `solution/model_new.py`
- `scripts/output/profile_latest.txt`
- `experiments/profile.md`
- `experiments/summary.md` 与 `experiments/LESSONS.md`

### 主要输出

- `experiments/workload_profile.md`

### 适合什么时候调用

- 不确定当前算子的真正热点是算力、访存、layout 还是调度开销。
- 有多个候选优化目标，但不知道该优先做哪个。
- 同一个目标尝试多次后，想判断该继续重试还是切换方向。

## `research`

### 核心作用

- 在干净上下文中重新审视当前状态。
- 结合代码、实验历史、profiling 和 workload 分析，诊断为什么当前方向进入平台期或反复失败。
- 为下一轮实验生成一份结构化计划。

### 主要输入

- `solution/model.py`
- `solution/model_new.py`
- `experiments/summary.md`
- `experiments/LESSONS.md`
- `experiments/profile.md`
- `experiments/workload_profile.md`
- `scripts/output/profile_latest.txt`
- 各轮 `exp_N/plan.md` 与 `exp_N/result.md`

### 主要输出

- `experiments/exp_N/plan.md`

### 适合什么时候调用

- 多轮实验进入平台期，提升幅度很小。
- 出现重复试错或明显在兜圈子。
- 正确性问题持续出现，需要重新规划方法。
- 需要系统地定义下一轮实验，而不是继续凭感觉微调。

## 三者如何配合

一个典型链路如下：

1. 先通过 `bash scripts/run.sh full` 生成最新 profiling。
2. 调用 `profiler`，确认当前主要瓶颈。
3. 如果需要更进一步判断目标优先级，再调用 `workload-inspector`。
4. 如果已经进入平台期或需要完整重规划，再调用 `research` 生成下一轮 `plan.md`。

## 它们与主循环的关系

- 子 Agent 不直接改优化代码。
- 子 Agent 通过磁盘产物和主循环协作，而不是通过临时聊天上下文传递关键结论。
- 主循环负责实现、验证、测量和记录；子 Agent 负责诊断、选目标和做计划。

## 读者应形成的理解

- `profiler` 更像“瓶颈分析师”。
- `workload-inspector` 更像“目标选择器”。
- `research` 更像“实验规划师”。
- 三者一起让优化循环更少拍脑袋，更依赖证据。

## 延伸阅读

- [总体工作流](workflow-overview.md)
- [流程控制机制](control-flow.md)
- [实验记录机制](experiment-management.md)
