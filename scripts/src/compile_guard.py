"""
Compile-guarded import of ModelNew with timeout protection.

Uses SIGALRM to detect compilation hangs. On timeout or compile failure,
clears the build cache and exits.
"""

import os
import shutil
import signal
import sys


class CompileTimeoutError(Exception):
    """Raised when ModelNew compilation exceeds the timeout."""
    pass


def _timeout_handler(signum, frame):
    raise CompileTimeoutError()


def clear_compile_cache(ext_name: str = "softmax_v2"):
    """Remove torch cpp_extension build cache for the given extension."""
    try:
        from torch.utils.cpp_extension import get_default_build_root
        build_root = get_default_build_root()
    except Exception:
        build_root = os.path.join(os.path.expanduser("~"), ".cache", "torch_extensions")

    cleared = False
    if os.path.isdir(build_root):
        for sub in os.listdir(build_root):
            cache_dir = os.path.join(build_root, sub, ext_name)
            if os.path.isdir(cache_dir):
                shutil.rmtree(cache_dir)
                print(f"Cleared compile cache: {cache_dir}")
                cleared = True
    if not cleared:
        print("No matching compile cache found, nothing to clear.")


def import_model_new(timeout: int = 300):
    """
    Import ModelNew with compile-timeout protection.

    Args:
        timeout: Compile timeout in seconds (default 300).

    Returns:
        The ModelNew class.

    Raises:
        SystemExit: On compile timeout or compile failure.
    """
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)
    try:
        print(f"Compiling ModelNew (timeout {timeout}s)...")
        from model_new import Model as ModelNew
        signal.alarm(0)
        print("ModelNew compiled successfully.")
        return ModelNew
    except CompileTimeoutError:
        signal.alarm(0)
        print(f"❌ ModelNew compile timeout (>{timeout}s), process may be stuck.")
        print("Clearing compile cache for next attempt...")
        clear_compile_cache()
        print("Please fix the CUDA kernel code and retry.")
        sys.exit(1)
    except Exception as exc:
        signal.alarm(0)
        print(f"❌ ModelNew compile failed: {exc}")
        print("Clearing compile cache for next attempt...")
        clear_compile_cache()
        print("Please fix the error above and retry.")
        sys.exit(1)
