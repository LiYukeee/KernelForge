# /benchmark

| 参数 | 命令 | 使用场景 |
|---|---|---|
| `correctness` | `bash scripts/run.sh correctness` | 仅验证正确性 |
| `quick`（默认） | `bash scripts/run.sh quick` | 正确性 + 性能（100 次迭代，无 profiling） |
| `full` | `bash scripts/run.sh full` | 正确性 + 性能（1000 次迭代）+ profiling |

输出自动保存到 `scripts/output/bench_latest.log`；`full` 模式的 profiling 结果保存到 `scripts/output/profile_latest.txt`。`/log-experiment` 会附上这些文件。

如果运行超时或编译卡住（`compile_guard` 默认 300 秒超时），脚本会自动清理编译缓存并退出。

汇报内容：
- 正确性测试通过/失败及最大误差
- Model / ModelNew / Model (compiled) 平均延迟 (ms)
- 加速比：`speedup(new/base)` 和 `speedup(compile/base)`
