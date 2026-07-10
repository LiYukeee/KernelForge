# 项目定位与适用场景

本章回答两个最容易被误解的问题：`KernelForge` 到底是在做什么，以及当前 `solution/` 里的代码是不是项目的真实目标。理解这一章之后，读者应该明确知道这不是一个“只做 ReLU 优化”的仓库，而是一套可以反复复用的算子优化模板。

## KernelForge 是什么

- `KernelForge` 是一个面向单算子的优化模板。
- 它把“算子实现”“评测脚本”“流程控制”“实验记录”拆开，形成一个稳定的优化工作台。
- 项目目标不是提供某个固定算子的最优实现，而是提供一套可复用的优化闭环。

## 为什么说它是模板

- `solution/model.py` 用来放参考实现。
- `solution/model_new.py` 用来放优化实现。
- `scripts/`、`.claude/commands/`、`.claude/hooks/` 提供的是围绕这两个文件工作的固定基础设施。
- 换一个算子时，通常不需要重写整套评测流程，只需要替换 `solution/` 中的内容。

## 当前 `solution/` 只是示例

- 当前仓库里的 `solution/model.py` 和 `solution/model_new.py` 只是一个示例对。
- 它们当前演示的是一个简单的 `ReLU` 算子接入方式，而不是项目的唯一优化对象。
- 示例的作用是说明模板接口应该长什么样，以及脚本如何调用它。

## 与 KernelBench 的关系

- 项目默认面向从 `KernelBench` 中抽取算子进行优化的工作流。
- `KernelBench` 不同 level 的算子都可以按这套模板接入到 `solution/` 中。
- 接入后，统一复用 `scripts/run.sh`、`scripts/run.py` 和实验记录机制，不需要为每个算子重新搭评测框架。

## 平台支持与侧重点

- 项目同时支持 NVIDIA 与 Metax GPU。
- 支持路径体现在 `scripts/env.sh` 与 `scripts/src/gpu_selector.py` 中，分别处理 `nvidia-smi` 与 `mx-smi` 分支。
- 虽然支持两类平台，但项目的叙述重点、环境理解和实践建议应以 Metax 为主。

## 适合什么场景

- 想把一个 `KernelBench` 算子快速放入统一优化闭环。
- 想在固定环境中比较参考实现和优化实现的正确性与性能。
- 想把实验结果持续归档，避免重复试错。

## 不适合什么场景

- 把它当成完整训练框架或通用深度学习项目来使用。
- 频繁修改 `scripts/` 或评测规则本身。
- 一边优化算子，一边随意改依赖、换环境或绕过统一入口。

## 延伸阅读

- [架构总览](architecture-overview.md)
- [新算子接入方式](new-operator-integration.md)
- [环境与平台重点](environment-and-platform.md)
