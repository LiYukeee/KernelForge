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
