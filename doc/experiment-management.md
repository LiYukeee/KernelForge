# 实验记录机制

本章解释为什么这个项目不仅要求“跑一次 benchmark”，还要求把实验过程系统地记录下来。对 KernelForge 来说，实验归档不是附属动作，而是模板的一部分，它决定了经验能否积累、失败能否复盘、重复劳动能否减少。

## `/log-experiment` 的职责

- 为最近一次实验建立快照。
- 保存代码、benchmark 日志和 profiling 结果。
- 补充文字化结论，说明本轮改了什么、结果如何、接下来该怎么做。

## 单次实验目录里有什么

按 `.claude/commands/log-experiment.md` 的约定，实验目录通常包含：

- `model_new.py`：本轮实验对应的代码快照
- `bench.log`：最近一次 benchmark 日志
- `profile.txt`：最近一次 profiling 结果，若存在
- `result.md`：本轮实验的总结

## 子 Agent 还会产出什么

除了单次实验目录，本项目现在还有几类面向循环优化的长期分析产物：

- `experiments/profile.md`：由 `profiler` 子 Agent 维护，概括当前 `model_new.py` 的 profiling 结论与最大瓶颈。
- `experiments/workload_profile.md`：由 `workload-inspector` 子 Agent 维护，记录输入形状、布局、热点和下一步目标建议。
- `experiments/exp_N/plan.md`：由 `research` 子 Agent 在需要时写入，用于规划下一轮实验。

这些文件和 `result.md` 的区别在于：

- `result.md` 记录“这一轮做了什么、结果如何”。
- `profile.md` 记录“当前时间主要花在哪”。
- `workload_profile.md` 记录“当前工作负载长什么样、下一个目标该是谁”。
- `plan.md` 记录“下一轮应该怎么做”。

## 为什么要有 `summary.md`

- `experiments/summary.md` 用来横向查看多轮实验。
- 它更适合看趋势，例如哪一轮是新最优、哪一轮只是消融、哪一轮被回退。
- 单次实验目录适合看细节，`summary.md` 适合看全局进展。

## 为什么要有 `LESSONS.md`

- `experiments/LESSONS.md` 用来沉淀跨实验的稳定经验。
- 它适合记录“以后应该继续做什么”或“以后应该避免什么”。
- 相比单次 `result.md`，这里更强调长期复用价值。

## 为什么失败实验也要记录

- 失败实验同样提供了边界信息。
- 如果不记录，后续很可能重复做相同尝试。
- 模板鼓励把失败当成可复用知识，而不是应被忽略的噪声。

## 这套机制解决什么问题

- 让优化过程可回溯。
- 让不同阶段的结果可比较。
- 让个人经验变成团队经验。
- 让主循环可以把测量、目标选择和实验规划分别沉淀成独立产物。

## 延伸阅读

- [总体工作流](workflow-overview.md)
- [验证与评测体系](evaluation-and-benchmarking.md)
- [流程控制机制](control-flow.md)
- [子 Agent 协作机制](sub-agents.md)
