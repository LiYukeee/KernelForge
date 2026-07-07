"""
Auto-select the CUDA device with the most free memory.

Must be called before any CUDA initialization (including load_inline).
"""

import os
import subprocess

import numpy as np


def auto_choose_cuda_device():
    """Query GPU memory usage via nvidia-smi and pick the least used device."""
    try:
        cmd = 'nvidia-smi -q -d Memory |grep -A4 GPU|grep Used'
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE).stdout.decode().split('\n')
        os.environ['CUDA_VISIBLE_DEVICES'] = str(
            np.argmin([int(x.split()[2]) for x in result[:-1]])
        )
        print(f'--- Auto chose CUDA device {os.environ["CUDA_VISIBLE_DEVICES"]} ---')
    except Exception:
        print('--- Failed to auto choose CUDA device, using default ---')

def auto_choose_maca_device():
    """Query GPU memory usage via mx-smi and pick the least used device."""
    try:
        result = subprocess.run(
            ['mx-smi'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True
        ).stdout.splitlines()

        devices = []
        memory_used = []
        current_gpu = None

        for line in result:
            line = line.strip()
            if not line.startswith('|'):
                continue

            gpu_match = re.match(r'^\|\s*(\d+)\b', line)
            if gpu_match:
                current_gpu = int(gpu_match.group(1))
                continue

            if current_gpu is None:
                continue

            mem_match = re.search(r'(\d+)\s*/\s*\d+\s*MiB', line)
            if mem_match:
                devices.append(current_gpu)
                memory_used.append(int(mem_match.group(1)))
                current_gpu = None

        if not devices:
            raise ValueError('No GPU memory usage data found')

        best = devices[int(np.argmin(memory_used))]
        os.environ['MACA_VISIBLE_DEVICES'] = str(best)
        print(f'--- Auto chose MACA device {best} ---')
    except Exception:
        print('--- Failed to auto choose MACA device, using default ---')

def auto_choose_gpu():
    """Auto-select the GPU device with the most free memory."""
    auto_choose_cuda_device()
    auto_choose_maca_device()