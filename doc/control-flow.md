# 流程控制机制

本章解释项目如何通过命令、Hook 和运行入口把优化流程收敛到一条稳定的路径上。权限模型回答“什么不能做”，而流程控制回答“系统如何阻止你偏离推荐流程”。

## 三层控制

- 命令层：定义标准工作流。
- 代理层：提供专门的诊断与规划能力。
- Hook 层：拦截越界操作。
- 运行层：固定 benchmark 入口和参数形式。

## 命令层

- `/optimize`：定义自主优化循环。
- `/benchmark`：定义 `correctness`、`quick`、`full` 三种运行模式。
- `/log-experiment`：定义实验快照与记录方式。
- 这些命令说明写在 `.claude/commands/` 下，对应的是推荐工作方法。

## Hook 层

### `pre_bash.sh`

- 拦截高风险命令，如 `git reset --hard`、`git push --force`。
- 拦截绕过 `scripts/run.sh` 直接调用 `scripts/run.py` 的做法。
- 校验 `scripts/run.sh` 的参数只能是 `correctness`、`quick`、`full`。

### `pre_edit.sh`

- 禁止编辑 `solution/model.py`。
- 禁止编辑 `scripts/`。
- 只允许在 `solution/` 下修改 `solution/model_new.py`。

### `stop.sh`

- 在会话结束前检查 `model_new.py` 是否比最新日志更新。
- 提醒是否缺少新的 benchmark 结果。
- 提醒是否缺少新的 profiling 结果。

## 代理层

- `profiler`：在“需要知道当前瓶颈在哪”时被动调用，读取 profiling 产物并把结论写入 `experiments/profile.md`。
- `workload-inspector`：在“需要判断下一步该优化哪个目标，或该继续重试还是切换方向”时调用，输出 `experiments/workload_profile.md`。
- `research`：在“出现平台期、重复实验、正确性墙或需要重做计划”时调用，最终写入新的实验 `plan.md`。
- 代理之间通过磁盘产物协作，而不是靠嵌套上下文直接传话；产物本身就是契约。

## 运行层

- 统一要求从 `bash scripts/run.sh` 进入 benchmark。
- 通过这一层保证环境加载、日志位置和模式参数的一致性。
- 这一层与 Hook 层配合，避免出现同一项目中存在多条不一致执行路径。

## 三层是如何配合的

- 命令层告诉你“推荐怎么做”。
- 代理层帮助你“在复杂分叉点做出更有依据的判断”。
- Hook 层阻止你“明显不该这么做”。
- 运行层保证“真正执行时还是走同一套底层链路”。

## 为什么这很重要

- 算子优化很容易因为命令、环境或记录方式不一致而造成假结论。
- 流程控制的作用就是尽量消除这种额外变量。
- 对模板来说，这和性能优化本身同样重要。

## 延伸阅读

- [权限模型](permission-model.md)
- [总体工作流](workflow-overview.md)
- [执行链路](execution-pipeline.md)
- [子 Agent 协作机制](sub-agents.md)
