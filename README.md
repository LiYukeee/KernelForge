# KernelForge

基于 Claude Code 的自主 CUDA 算子优化系统。通过 `/optimize` 命令驱动迭代优化循环，将 PyTorch 参考实现逐步替换为高性能自定义内核。

## 项目结构

```
KernelForge/
├── solution/
│   ├── model.py          # PyTorch 基线参考（不可编辑）
│   └── model_new.py      # 优化目标（唯一可编辑文件）
├── scripts/
│   ├── run.sh            # 入口脚本（环境配置 + 调用 run.py）
│   ├── run.py            # 测试运行器（正确性 / 性能 / profiling）
│   └── src/
│       ├── benchmark.py  # 正确性验证、性能测试、profiling 工具
│       ├── compile_guard.py  # 编译超时保护（默认 300s）
│       ├── gpu_selector.py   # 自动选择空闲 GPU
│       └── path_bootstrap.py # 路径初始化
├── experiments/          # 实验记录（由 /log-experiment 创建）
├── CLAUDE.md             # 项目指令（Claude Code 读取）
└── .claude/
    ├── commands/         # 斜杠命令定义
    │   ├── optimize.md   # /optimize — 主优化循环
    │   ├── benchmark.md  # /benchmark — 运行基准测试
    │   └── log-experiment.md  # /log-experiment — 记录实验
    ├── settings.json     # 权限与钩子配置
    └── skills/           # 辅助技能（CUDA profiling、知识库等）
```

## 工作流

### 1. 准备算子

将 KernelBench 中的算子模板复制到 `solution/` 目录：
- `model.py` — PyTorch 参考实现（基线，不可编辑）
- `model_new.py` — 优化目标（初始与 model.py 相同）

### 2. 运行基准测试

```bash
bash scripts/run.sh correctness   # 仅验证正确性
bash scripts/run.sh quick          # 正确性 + 性能（100 次迭代）
bash scripts/run.sh full           # 正确性 + 性能（1000 次迭代）+ profiling
```

输出保存到 `scripts/output/bench_latest.log`，profiling 结果保存到 `scripts/output/profile_latest.txt`。

### 3. 自主优化（推荐）

在 Claude Code 中使用 `/optimize` 命令启动自主优化循环：

```
/optimize
```

循环会自动执行：评估 → 规划 → 实现 → 验证 → 测量 → 记录 → 决策，持续迭代直到达到满意性能。

### 4. 手动迭代

也可以手动进行优化：

1. 编辑 `solution/model_new.py`，将 PyTorch 算子替换为自定义 CUDA 内核
2. `bash scripts/run.sh correctness` 验证正确性
3. `bash scripts/run.sh quick` 测量性能
4. `/log-experiment` 记录实验结果

## 命令

| 命令 | 用途 |
|---|---|
| `/optimize` | 启动自主优化循环 |
| `/benchmark <correctness\|quick\|full>` | 运行基准测试 |
| `/log-experiment` | 记录实验（快照 model_new.py + 日志 + result.md） |

## 优化规则

- **只编辑 `model_new.py`**，`model.py` 是语义锚点
- **一次只做一个优化**，小步快跑
- **加速路径**：手写 CUDA/C++（`torch.utils.cpp_extension.load_inline`）或 Triton
- **仅优化推理路径**（`model.eval()` + `torch.no_grad()`）
- **先关注绝对延迟，再看加速比**
- **保持环境固定**，不安装/卸载依赖

## 实验记录

`/log-experiment` 会在 `experiments/` 下创建编号文件夹，包含：

- `model_new.py` — 该次实验的代码快照
- `bench.log` — 基准测试日志
- `profile.txt` — profiling 结果（如有）
- `result.md` — 实验描述、结果、经验总结

实验汇总记录在 `experiments/summary.md`，跨实验洞察记录在 `experiments/LESSONS.md`。

## 环境要求

- CUDA 13.2+
- PyTorch (CUDA 版本)
- Python 3.10+

环境配置在 `scripts/run.sh` 中，如需修改请调整该文件顶部的变量。
