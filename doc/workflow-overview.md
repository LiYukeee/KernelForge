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

- 在 Claude Code 中使用 `/loop /optimize`，由 `/loop` 负责重复触发 `/optimize`。
- `/loop` 的调度机制属于 Claude Code，本仓库不实现调度器；本仓库只定义每次 `/optimize` 调用的工作方式。
- 每次 `/optimize` 都围绕 `评估 -> 规划 -> 实现 -> 正确性验证 -> 性能测量 -> 实验记录 -> 决策` 展开。

流程图：![`/loop /optimize` 自动优化流程](loop-optimize-flow.svg)

### `/loop /optimize` 的单轮流程

1. **评估当前状态。** 主 Agent 读取 `solution/model_new.py`、基线 `solution/model.py`、`experiments/summary.md`、`experiments/LESSONS.md` 和相关实验的 `result.md`。如果最高编号实验目录中存在 `plan.md` 但没有 `result.md`，优先实施该计划。
2. **选择一个优化点。** 每轮只做一个优化，结合当前算子特征、输入形状、内存访问模式、profiling 结果和历史实验，避免重复已经失败的方案。
3. **按需调用子 Agent。** 子 Agent 只负责分析和规划，不直接修改 `model_new.py`；它们通过磁盘产物向主 Agent 传递结论，具体触发条件见下一节。
4. **实现修改。** 主 Agent 只修改 `solution/model_new.py`。`pre_edit.sh` 会拒绝修改 `solution/model.py`、`scripts/` 和其他受保护文件。
5. **验证正确性。** 执行 `bash scripts/run.sh correctness`。该步骤会加载固定环境、编译 `ModelNew`，并要求最大绝对误差不超过 `1e-4`。编译或正确性失败时，停止本轮后续性能测试。
6. **测量性能。** 默认执行 `bash scripts/run.sh quick`：每个模型预热 20 次并测试 100 次。结果提升不足 5%、参考延迟异常或需要定位瓶颈时，再执行 `bash scripts/run.sh full`；`full` 测试 1000 次并生成 profiling 结果。
7. **记录实验。** 调用 `/log-experiment`，保存当前 `model_new.py`、最新 benchmark 日志、可用的 profiling 文件和 `result.md`，并更新 `experiments/summary.md`。失败实验和消融实验也必须记录。
8. **决定下一轮方向。** 明显提升则保留；小幅变化需重复确认；变慢或失败则回退或切换方向；进入平台期时调用 `research` 重新规划。
9. **继续循环。** `/loop` 再次触发 `/optimize`，下一轮从上一轮写入磁盘的代码、日志和实验记录继续。

### 子 Agent 的触发条件

三个子 Agent 都通过 Claude Code 的 `Agent` 工具按需调用，不是每轮固定执行，也不由 Hook 自动启动。

- **`profiler`：瓶颈分析。** 当主 Agent 不确定时间主要消耗在哪个阶段，或准备重写某个计算步骤前需要确认瓶颈时调用。它读取 `scripts/output/profile_latest.txt`，将热点和下一步优化 lever 写入 `experiments/profile.md`。它不应按固定频率调用；模型发生结构性变化后，旧 profiling 结论需要重新生成。
- **`workload-inspector`：目标选择。** 当主 Agent 不确定下一个应该优化哪个目标，或需要判断继续重试、切换目标还是跳过时调用。它分析 `get_inputs()`、输入布局、当前实现、profiling 热点和历史实验，并写入 `experiments/workload_profile.md`。如果 `research` 发现该文件缺失且计划依赖这些信息，必须先调用它并等待完成。
- **`research`：重新规划。** 在以下任一情况下调用：5 次以上实验结果都在约 5% 内波动形成平台期；连续 3 次采用不同方法仍然正确性失败；即将重复 `summary.md` 中已经失败的尝试；当前优化方向已经耗尽想法。它使用干净上下文从磁盘读取材料，写入下一轮 `experiments/exp_N/plan.md`。通常每 5～10 次实验至少调用一次，以避免循环原地打转。

典型的协作关系是：

```text
主 Agent 判断状态
├─ 不知道瓶颈在哪里 -> profiler
├─ 不知道下一个目标或是否切换 -> workload-inspector
└─ 平台期 / 重复失败 / 正确性墙 / 方向耗尽 -> research
                                      └─ 必要时先调用 workload-inspector
```

### 运行产物与停止行为

- 每次 benchmark 都通过 `scripts/run.sh`，并刷新 `scripts/output/bench_latest.log`。
- `full` 模式额外刷新 `scripts/output/profile_latest.txt`。
- `stop.sh` 在会话结束前检查 `model_new.py` 是否比最新日志或 profiling 文件更新，并给出补测提醒；它始终以成功状态退出，不会强制阻止停止。
- 仓库没有定义固定的自动停止性能阈值。实际停止通常来自用户终止 `/loop`，或主 Agent 判断当前目标已经达到预期。

## 子 Agent 在流程中的位置

- 这三个 Agent 的详细输入、输出和职责见[子 Agent 协作机制](sub-agents.md)。

## 这套流程想解决什么问题

- 让不同算子的优化方式统一下来。
- 让每次实验都能被验证和回溯。
- 让“优化代码”和“评测代码”保持清晰分离。

## 延伸阅读

- [执行链路](execution-pipeline.md)
- [验证与评测体系](evaluation-and-benchmarking.md)
- [实验记录机制](experiment-management.md)
- [子 Agent 协作机制](sub-agents.md)
