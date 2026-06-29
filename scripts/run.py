"""
Test runner for Model vs ModelNew.

1. Correctness test — compare outputs
2. Performance test — compare latency and speedup
3. Profile ModelNew — identify bottlenecks
"""

import torch
import sys
import os

from src.gpu_selector import auto_choose_cuda_device
from src.compile_guard import import_model_new
from src.benchmark import test_correctness, test_performance, profile_model_new
from src.path_bootstrap import ensure_solution_dir_on_path
ensure_solution_dir_on_path(__file__)
from model import Model, get_inputs, get_init_inputs

# --- Constants ---
WARM_UP_TIMES = 20
CORRECTNESS_THRESHOLD = 1e-4
COMPILE_TIMEOUT = 300
TEST_ITERATIONS = {"full": 1000, "quick": 100, "correctness": 0}
# -----------------

# Must set CUDA_VISIBLE_DEVICES before any CUDA initialization (including load_inline)
auto_choose_cuda_device()

# Import ModelNew with compile timeout protection
ModelNew = import_model_new(timeout=COMPILE_TIMEOUT)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "quick", "correctness"], default="full",
    help="full=1000iter+profiling(default), quick=100iter无profiling, correctness=仅正确性")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 0. 初始化
    init_inputs = [x for x in get_init_inputs()]
    model = Model(*init_inputs).to(device)
    model.eval()
    model_new = ModelNew(*init_inputs).to(device)
    model_new.eval()

    # 同步权重：Model 与 ModelNew 结构一致，直接按同名参数复制
    model_new.load_state_dict(model.state_dict())

    # torch.compile 版本（首次调用时触发追踪/编译，warmup 阶段会完成）
    print("正在创建 model_compile (torch.compile)...")
    model_compile = torch.compile(model)
    model_compile.eval()

    inputs = [x.to(device) for x in get_inputs()]

    # 1. 正确性测试
    max_diff = test_correctness(model, model_new, inputs)
    if max_diff <= CORRECTNESS_THRESHOLD:
        print(f"✅ 正确性测试通过：最大误差 {max_diff} <= {CORRECTNESS_THRESHOLD}")
    else:
        print(f"❌ 正确性测试失败：最大误差 {max_diff} > {CORRECTNESS_THRESHOLD}")
        exit(1)

    if args.mode == "correctness":
        print("CORRECTNESS_ONLY: PASS")
        exit(0)

    # 2. 性能测试
    perf_result = test_performance(
        model, model_new, model_compile,
        inputs, iterations=TEST_ITERATIONS[args.mode], warmup_times=WARM_UP_TIMES
    )
    if perf_result is None:
        print("❌ 性能测试失败，跳过后续步骤。")
        exit(1)

    model_time, model_new_time, model_compile_time, speedup = perf_result
    del model, model_compile
    torch.cuda.empty_cache()

    # 3. Profiling
    if args.mode == "full":
        profile_model_new(model_new, inputs,
                          profile_output="output/profile_latest.txt")
        torch.cuda.empty_cache()

    # 4. 输出最终性能结果
    print(
        f"FINAL_SPEED_RESULT: "
        f"model={model_time * 1000:.6f} ms, "
        f"model_new={model_new_time * 1000:.6f} ms, "
        f"model_compile={model_compile_time * 1000:.6f} ms, "
        f"speedup(compile/base)={model_time / model_compile_time:.2f}x, "
        f"speedup(new/base)={speedup:.2f}x"
    )
