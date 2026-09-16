# KernelForge LangChain

KernelForge LangChain 是一个面向 GPU 算子优化的多 Agent 实验框架。它以
KernelBench 风格的 `model.py` 为基线，通过 PLAN、CODE、LOG 三个阶段迭代生成
并验证 `model_new.py`，同时保存每轮计划、实现、性能数据和经验总结。

## 工作流程

每轮实验依次执行以下阶段：

1. **PLAN**：分析基线实现、当前优化实现、设备信息和历史实验，生成本轮优化计划。
2. **CODE**：按照计划修改 `model_new.py`，通过 benchmark 检查正确性和性能；失败时根据诊断自动修复，最多重试 10 次。
3. **LOG**：归档本轮实现，更新累计经验和实验汇总。

CODE 阶段即使最终 benchmark 失败，也会进入 LOG 阶段保存本轮结果，方便后续轮次继续分析和优化。

## 环境要求

- Linux 和 Bash
- 可用的 GPU/加速卡及对应驱动
- Agent 运行环境：Python、`langchain`、`deepagents`、`python-dotenv`、`rich`
- Benchmark 运行环境：Python、PyTorch、NumPy，以及算子实现需要的 Triton 或 CUDA 工具链
- 批量并行运行时还需要 [GNU Parallel](https://www.gnu.org/software/parallel/)

项目目前没有依赖清单，Agent 环境和 benchmark 环境需要提前准备。二者可以是不同的 Python 环境：启动 `run_experiments.py` 的 Python 负责运行 Agent，`.env` 中的 `PYTHON_BIN` 专门负责执行 benchmark 和 profiler。

## 配置

首先在项目根目录复制环境变量模板：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```dotenv
# 默认算子目录。相对路径以 scripts/ 目录为基准
TARGET="../solution/sample_relu"

# Agent 使用的模型
MODEL_NAME="your-model-name"
BASE_URL="https://your-api-endpoint/v1"
API_KEY="your-api-key"
MODEL_PROVIDER="deepseek"

# Benchmark 使用的 Python 和 CUDA 环境
PYTHON_BIN="/path/to/benchmark-env/bin/python"
TORCH_CUDA_ARCH_LIST="12.0"
CUDA_HOME="/usr/local/cuda"
PATH="$CUDA_HOME/bin:$PATH"
LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

# 可选：LangSmith tracing
LANGSMITH_TRACING="true"
LANGSMITH_API_KEY="your-langsmith-api-key"
LANGSMITH_PROJECT="kernel-forge-dev"
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"

# true 时实时输出 Agent 的消息、工具调用和 token 使用信息
PRINT_ALL="true"
```

`MODEL_NAME`、`BASE_URL` 和 `API_KEY` 必须与 `MODEL_PROVIDER` 对应的 LangChain 模型后端匹配。若不使用 LangSmith，可将 `LANGSMITH_TRACING` 设为 `false` 并留空相关字段。

## 算子目录格式

每个实验目录至少需要以下两个文件：

```text
solution/<task>/
├── model.py       # 固定的 PyTorch 基线实现
└── model_new.py   # Agent 持续修改的候选实现
```

两个文件都应定义 KernelBench 接口：

- `Model`：待测试的模型类
- `get_init_inputs()`：构造 `Model` 所需的参数
- `get_inputs()`：单次 forward 的输入

仓库中的 `solution/sample_relu` 是从 KernelBench 提取的最小样例，可以直接用来检查配置和完整流程。

## 运行单个实验

在项目根目录执行：

```bash
python run_experiments.py \
  --target solution/sample_relu \
  --rounds 10
```

参数说明：

- `--target`：算子目录，必须包含 `model.py` 和 `model_new.py`；相对路径以当前工作目录为基准。
- `--rounds N`：要完成的最终绝对轮次，默认为 `10`。它不是“再运行 N 轮”；例如已有 3 轮时传入 `--rounds 10`，程序会从第 4 轮继续执行到第 10 轮。

程序支持断点续跑：完整轮次会被跳过；如果最新轮次已有 `plan.md` 但尚未完成，程序会从 CODE 阶段继续。为避免覆盖不一致的结果，轮次目录必须从 `round_1` 开始连续，且只有最新一轮可以处于未完成状态。

## 批量并行运行

`scripts/run_experiments_parallel.sh` 会扫描同一层级下的所有实验目录，并使用 GNU Parallel 并发执行。运行前直接编辑脚本顶部的配置：

```bash
experiment_root="$PROJECT_ROOT/solution/L1"  # 待扫描的目录
rounds=10                                    # 最终绝对轮次
n_jobs=1                                     # 最大并发任务数
delay_time=20                                # 相邻任务启动间隔（秒）
python_command="python"                      # Agent 环境的 Python
log_filename="run_experiments.log"
```

然后运行：

```bash
bash scripts/run_experiments_parallel.sh
```

脚本只处理 `experiment_root` 的直接子目录，并跳过缺少 `model.py` 或 `model_new.py` 的目录。每个任务的标准输出和错误输出会写入：

```text
<experiment>/log/run_experiments.log
```

并发任务通常会争用 GPU。请结合可用设备数量、显存和 API 限流设置 `n_jobs` 与 `delay_time`；脚本本身不会为不同任务自动绑定不同 GPU。

## 从 KernelBench 准备任务

`scripts/prepare_solutions.py` 可以将 KernelBench 的任务文件初始化为实验目录。默认读取项目同级的 `../kernels/level{1,2,3}`，写入 `solution/L{1,2,3}`。

先预览变更：

```bash
python scripts/prepare_solutions.py --dry-run
```

准备指定级别：

```bash
python scripts/prepare_solutions.py --levels 1 2
```

也可以显式指定目录：

```bash
python scripts/prepare_solutions.py \
  --kernels-root /path/to/KernelBench/KernelBench \
  --solution-root ./solution \
  --levels 1 2 3
```

脚本会把每个源任务同时复制为 `model.py` 和 `model_new.py`。重复执行时会保留已有的 `model_new.py`；如果已有 `model.py` 与源文件不一致，则会在写入前终止，避免基线漂移。

## 输出文件

一次实验运行后，目标目录大致如下：

```text
solution/<task>/
├── model.py
├── model_new.py
├── bench_output/
│   ├── bench_latest.log
│   └── torch_profile_latest.txt
├── exp/
│   ├── lessons.md
│   ├── summary.md
│   ├── round_1/
│   │   ├── plan.md
│   │   ├── code.md
│   │   └── model_new.py
│   └── round_2/
│       └── ...
└── log/
    ├── token_usage.jsonl
    └── run_experiments.log   # 使用并行脚本时生成
```

- `bench_latest.log`：最近一次正确性与性能测试的原始输出。
- `torch_profile_latest.txt`：最近一次 profiler 汇总。
- `exp/round_N/plan.md`：第 N 轮优化计划。
- `exp/round_N/code.md`：CODE 阶段状态、benchmark 结果和 Agent 报告。
- `exp/round_N/model_new.py`：第 N 轮结束时的实现快照。
- `exp/lessons.md`：跨轮次累计的优化经验。
- `exp/summary.md`：各轮延迟、加速比和正确性汇总。
- `log/token_usage.jsonl`：各轮各阶段的模型调用和 token 使用记录。

## 独立运行 Benchmark 和 Profiler

不启动 Agent 也可以验证当前 `.env` 中 `TARGET` 指向的实现：

```bash
# 完整性能测试：warmup=200，repeat=500
bash scripts/bench.sh full

# 快速性能测试：warmup=20，repeat=100
bash scripts/bench.sh quick

# 最小正确性检查：warmup=0，repeat=1
bash scripts/bench.sh correctness

# 显式指定基线和候选文件
bash scripts/bench.sh quick \
  --v0-file solution/sample_relu/model.py \
  --v1-file solution/sample_relu/model_new.py
```

对候选实现执行 profiler：

```bash
bash scripts/profile.sh --warmup 200 --iterations 10
```

收集与 benchmark 环境一致的系统和设备信息：

```bash
bash scripts/get_system_info.sh
```

Benchmark 会比较两份实现的递归输出，浮点张量默认使用 `atol=1e-2`、`rtol=1e-2`，正确性通过后报告两者延迟中位数和 `speedup = baseline / candidate`。

