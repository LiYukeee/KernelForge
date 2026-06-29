"""
Benchmarking utilities for comparing Model vs ModelNew.

Provides correctness validation, performance timing, and torch profiler integration.
"""

import os
import time

import torch


def test_correctness(model, model_new, inputs):
    """Compare outputs of model and model_new, return max absolute difference."""
    print("正在进行正确性测试...")
    with torch.no_grad():
        output = model(*inputs)
        output_new = model_new(*inputs)

    # Compare in chunks to avoid allocating a temporary tensor as large as output
    max_diff = 0.0
    chunk = 256
    for i in range(0, output.shape[0], chunk):
        diff = (output[i:i+chunk] - output_new[i:i+chunk]).abs().max().item()
        max_diff = max(max_diff, diff)
    del output, output_new
    torch.cuda.empty_cache()

    print(f"最大误差: {max_diff}")
    return max_diff


def _bench_single(m, inputs, name, iterations, warmup_times=20):
    """Warmup + time a single model, return average seconds per iteration."""
    print(f"正在进行 {name} Warmup...")
    with torch.no_grad():
        for _ in range(warmup_times):
            m(*inputs)
    torch.cuda.synchronize()
    print(f"正在测试 {name}...")
    with torch.no_grad():
        start_time = time.time()
        for _ in range(iterations):
            m(*inputs)
        torch.cuda.synchronize()
    t = (time.time() - start_time) / iterations
    print(f"{name} 平均耗时: {t * 1000:.6f} ms")
    return t


def test_performance(model, model_new, model_compile, inputs, iterations=1000, warmup_times=20):
    """Benchmark all three models and compute speedup ratios."""
    try:
        print(f"正在进行性能测试 (迭代次数: {iterations})...")

        model_time         = _bench_single(model,         inputs, "Model",            iterations, warmup_times)
        model_new_time     = _bench_single(model_new,     inputs, "ModelNew",         iterations, warmup_times)
        model_compile_time = _bench_single(model_compile, inputs, "Model (compiled)", iterations, warmup_times)

        baseline = model_time
        speedup  = baseline / model_new_time
        print(f"\n加速比汇总（以 Model 为基准）:")
        print(f"  ModelNew:              {speedup:.2f}x")
        print(f"  Model (compiled):      {baseline / model_compile_time:.2f}x")

        return model_time, model_new_time, model_compile_time, speedup
    except Exception as e:
        print(f"❌ 性能测试过程中出现错误: {e}")
        return None


def profile_model_new(model_new, inputs, profile_output=None):
    """Run torch.profiler on ModelNew and optionally save the result."""
    print("正在对 ModelNew 进行 Profiling...")
    with torch.no_grad(), torch.profiler.profile(
        activities=[
            torch.profiler.ProfilerActivity.CPU,
            torch.profiler.ProfilerActivity.CUDA,
        ],
        record_shapes=True,
        with_stack=True
    ) as prof:
        for _ in range(10):
            model_new(*inputs)

    table = prof.key_averages().table(sort_by="cuda_time_total", row_limit=10)
    # print(table)
    if profile_output:
        os.makedirs(os.path.dirname(profile_output) or ".", exist_ok=True)
        with open(profile_output, "w") as f:
            f.write(table)
        print(f"Profiling 结果已保存到 {profile_output}")
