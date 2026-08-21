"""Profile the optimized model without changing the benchmark loader."""

import argparse
import os
from pathlib import Path

import torch

from bench import (
    _detect_target_device,
    _move_to_device,
    build_case,
    clone_value,
    sync_devices,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Profile ModelNew with torch.profiler.")
    parser.add_argument("--v0_file", type=Path, required=True)
    parser.add_argument("--v1_file", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--iterations", type=int, default=10)
    return parser.parse_args()


def profile_model_new(model_new, inputs, profile_output, iterations):
    """Run torch.profiler on ModelNew and save its CUDA summary."""
    print("Profiling ModelNew...")
    sync_devices()
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
            model_new(*inputs)
    sync_devices()

    table = prof.key_averages().table(sort_by="cuda_time_total", row_limit=10)
    profile_output.parent.mkdir(parents=True, exist_ok=True)
    profile_output.write_text(table, encoding="utf-8")
    print(f"Profiling result saved to {profile_output}")


def main():
    args = parse_args()
    if args.iterations <= 0:
        raise SystemExit("--iterations must be > 0.")

    v0_path = args.v0_file.resolve()
    v1_path = args.v1_file.resolve()
    model, model_new, v0_inputs, v1_inputs = build_case(v0_path, v1_path, args.seed)
    target_device = _detect_target_device(model, model_new, v0_inputs, v1_inputs)

    try:
        model_new.load_state_dict(model.state_dict())
    except Exception:
        pass

    model_new = model_new.to(target_device)
    inputs = clone_value(_move_to_device(v0_inputs, target_device))
    profile_model_new(model_new, inputs, args.profile_output.resolve(), args.iterations)


if __name__ == "__main__":
    main()
