# 架构总览

本章的目标是帮助读者建立一张“仓库地图”，知道哪些目录负责算子本身，哪些目录负责评测与流程，哪些部分是固定基础设施。读完之后，读者应该能快速判断一个问题大概属于哪一层，而不是在整个仓库里盲目查找。

## 四层结构

- 算子层：`solution/`
- 评测层：`scripts/`
- 流程层：`.claude/commands/`
- 代理层：`.claude/agents/`
- 约束层：`.claude/settings.json` 与 `.claude/hooks/`

## `solution/`：算子接入层

- `solution/model.py` 存放 PyTorch 参考实现。
- `solution/model_new.py` 存放优化目标实现。
- 对模板来说，这一层是最常替换的部分。
- 对当前仓库来说，这一层只是一个示例，不代表固定业务逻辑。

## `scripts/`：统一评测层

- `scripts/run.sh` 是统一入口，负责环境准备和模式分发。
- `scripts/env.sh` 负责设置平台相关环境变量和 Python 路径。
- `scripts/run.py` 负责组织正确性、性能和 profiling 的执行。
- `scripts/src/benchmark.py`、`compile_guard.py`、`gpu_selector.py`、`path_bootstrap.py` 分别负责测量、编译保护、GPU 选择和导入路径初始化。

## `.claude/commands/`：流程定义层

- `optimize.md` 定义自主优化循环。
- `benchmark.md` 定义统一 benchmark 命令的含义。
- `log-experiment.md` 定义实验记录规范。
- 这一层不是算子代码本身，而是围绕优化过程的“工作方法定义”。

## `.claude/agents/`：分析协作层

- `profiler.md` 定义 `profiler` 子 Agent，负责读取本地 profiling 产物并指出当前最大瓶颈。
- `workload_inspector.md` 定义 `workload-inspector` 子 Agent，负责结合输入形状、数据布局、profiling 热点和历史实验来判断“下一步该优化哪个目标”。
- `research.md` 定义 `research` 子 Agent，负责在干净上下文中综合磁盘产物，生成下一轮实验计划。
- 这一层不直接写优化代码，而是为主循环提供诊断、目标选择和计划建议。

## `.claude/settings.json` 与 `.claude/hooks/`：约束层

- `.claude/settings.json` 定义权限边界与 Hook 注册。
- `pre_bash.sh` 拦截不符合规则的命令。
- `pre_edit.sh` 拦截越界编辑。
- `stop.sh` 在会话结束前提示是否缺少最新验证或 profiling。

## 哪些是可替换的

- `solution/model.py`
- `solution/model_new.py`
- 与某个具体算子相关的输入构造逻辑

## 哪些是固定基础设施

- `scripts/run.sh` 的统一入口角色
- `scripts/` 中的评测与日志逻辑
- `.claude/settings.json` 中的权限边界
- `.claude/hooks/` 中的流程护栏
- `.claude/agents/` 中的辅助分析角色

## 为什么要这样分层

- 让“换算子”和“换流程”变成两件不同的事。
- 让每次优化的变化尽量集中在 `solution/`，而不是扩散到整个仓库。
- 让评测、记录和权限控制可以跨不同算子复用。
- 让复杂诊断任务可以交给专门的子 Agent，而不是把所有判断都堆在主循环里。

## 延伸阅读

- [总体工作流](workflow-overview.md)
- [子 Agent 协作机制](sub-agents.md)
- [权限模型](permission-model.md)
- [流程控制机制](control-flow.md)
