"""Profile one optimized model without requiring a baseline model."""

import argparse
from pathlib import Path

import torch

from bench import (
    _detect_target_device,
    _move_to_device,
    as_args,
    call_with_context,
    clone_value,
    load_ks_module,
    require_attr,
    set_seed,
    sync_devices,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Profile the V1 optimized model with torch.profiler."
    )
    parser.add_argument("--v1_file", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--iterations", type=int, default=10)
    return parser.parse_args()


def profile_model(model, inputs, profile_output, warmup, iterations):
    """Warm up and profile the V1 model, then save its CUDA summary."""
    print(f"Warming up V1 optimized model ({warmup} iterations)...")
    with torch.no_grad():
        for _ in range(warmup):
            model(*inputs)
    sync_devices()

    print("Profiling V1 optimized model...")
    with torch.no_grad(), torch.profiler.profile(
        activities=[
            torch.profiler.ProfilerActivity.CPU,
            torch.profiler.ProfilerActivity.CUDA,
        ],
        record_shapes=True,
        with_stack=True,
        acc_events=True,
    ) as prof:
        for _ in range(iterations):
            model(*inputs)
    sync_devices()

    table = prof.key_averages().table(sort_by="cuda_time_total", row_limit=10)
    profile_output.parent.mkdir(parents=True, exist_ok=True)
    profile_output.write_text(table, encoding="utf-8")
    print(f"Profiling result saved to {profile_output}")


def main():
    args = parse_args()
    if args.warmup < 0:
        raise SystemExit("--warmup must be >= 0.")
    if args.iterations <= 0:
        raise SystemExit("--iterations must be > 0.")

    v1_path = args.v1_file.resolve()
    v1_module = load_ks_module(v1_path)
    model_cls = require_attr(v1_module, "Model", v1_path)
    get_init_inputs = require_attr(v1_module, "get_init_inputs", v1_path)
    get_inputs = require_attr(v1_module, "get_inputs", v1_path)

    set_seed(args.seed)
    init_args = as_args(
        call_with_context(get_init_inputs, f"{v1_path}: get_init_inputs()"),
        f"{v1_path}: get_init_inputs()",
    )
    model = call_with_context(
        lambda: model_cls(*init_args), f"{v1_path}: Model(...)"
    )
    if hasattr(model, "eval"):
        model.eval()

    set_seed(args.seed)
    inputs = as_args(
        call_with_context(get_inputs, f"{v1_path}: get_inputs()"),
        f"{v1_path}: get_inputs()",
    )
    target_device = _detect_target_device(model, None, inputs, None)
    if hasattr(model, "to"):
        model = model.to(target_device)
    inputs = clone_value(_move_to_device(inputs, target_device))
    profile_model(
        model,
        inputs,
        args.profile_output.resolve(),
        args.warmup,
        args.iterations,
    )


if __name__ == "__main__":
    main()
