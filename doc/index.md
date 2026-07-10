# KernelForge 文档总览

这套文档面向第一次接触 KernelForge 的读者，重点解释项目是什么、为什么这样设计，以及应该如何理解它的约束与流程。当前 `solution/` 里的两个文件只是示例，本项目本质上是一个可复用的算子优化模板，而不是单一算子的最终工程。

## 一句话定义

`KernelForge` 是一个围绕 `solution/model.py` 与 `solution/model_new.py` 搭建的算子优化模板，用统一的脚本、权限和流程控制机制来支持接入、优化、评测和记录不同来源的算子。

## 先看什么

建议按下面顺序阅读：

1. [项目定位与适用场景](project-positioning.md)
2. [架构总览](architecture-overview.md)
3. [总体工作流](workflow-overview.md)
4. [权限模型](permission-model.md)
5. [流程控制机制](control-flow.md)
6. [验证与评测体系](evaluation-and-benchmarking.md)
7. [实验记录机制](experiment-management.md)
8. [环境与平台重点](environment-and-platform.md)
9. [子 Agent 协作机制](sub-agents.md)
10. [新算子接入方式](new-operator-integration.md)

## 文档导航

- [项目定位与适用场景](project-positioning.md)：理解模板定位、与 KernelBench 的关系，以及为什么文档以 Metax 为主线。
- [架构总览](architecture-overview.md)：理解 `solution/`、`scripts/`、`.claude/` 之间如何分工。
- [总体工作流](workflow-overview.md)：理解一次完整优化循环是如何推进的。
- [执行链路](execution-pipeline.md)：理解 `scripts/run.sh -> env.sh -> run.py -> benchmark.py` 的调用过程。
- [权限模型](permission-model.md)：理解哪些文件不能改、哪些操作被禁止。
- [流程控制机制](control-flow.md)：理解命令、Hook 和运行入口如何共同约束流程。
- [验证与评测体系](evaluation-and-benchmarking.md)：理解 `correctness`、`quick`、`full` 三种模式及其指标。
- [实验记录机制](experiment-management.md)：理解 `/log-experiment`、`experiments/summary.md` 与 `LESSONS.md` 的作用。
- [环境与平台重点](environment-and-platform.md)：理解 NVIDIA 与 Metax 的双分支支持，以及 Metax 优先的叙述重点。
- [子 Agent 协作机制](sub-agents.md)：理解 `profiler`、`research`、`workload-inspector` 三个子 Agent 如何辅助优化循环。
- [新算子接入方式](new-operator-integration.md)：理解如何把 KernelBench 的新算子放进这套模板。

## 阅读提示

- 如果你想先知道项目是做什么的，优先读“项目定位”和“架构总览”。
- 如果你想先知道怎么跑起来，优先读“总体工作流”和“执行链路”。
- 如果你想先知道规则边界，优先读“权限模型”和“流程控制机制”。

## 延伸阅读

- [项目定位与适用场景](project-positioning.md)
- [架构总览](architecture-overview.md)
- [总体工作流](workflow-overview.md)
