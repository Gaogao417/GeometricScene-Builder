"""Runtime configuration helpers for local model and Wolfram execution."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Optional


WINDOWS_WOLFRAM_KERNELS = [
    "D:/Program Files/Wolfram Research/Wolfram/14.3/wolfram.exe",
    "C:/Program Files/Wolfram Research/Wolfram/14.3/wolfram.exe",
    "C:/Program Files/Wolfram Research/Wolfram/14.2/wolfram.exe",
    "C:/Program Files/Wolfram Research/Wolfram/14.1/wolfram.exe",
    "C:/Program Files/Wolfram Research/Wolfram/14.0/wolfram.exe",
]

MACOS_WOLFRAM_KERNELS = [
    "/Applications/Wolfram.app/Contents/MacOS/WolframKernel",
    "/Applications/Mathematica.app/Contents/MacOS/WolframKernel",
    "/Applications/Wolfram Engine.app/Contents/MacOS/WolframKernel",
]


def resolve_wolfram_kernel(config_value: Optional[str] = None) -> str:
    """Resolve a Wolfram kernel executable for Windows/macOS/Linux.

    Precedence:
    1. Explicit request/config value.
    2. Environment variables.
    3. Well-known Windows/macOS install paths.
    4. PATH lookup.
    5. Platform default path for clear error messages.
    """
    if config_value:
        return config_value

    for env_name in ("GSB_WL_KERNEL", "WOLFRAM_KERNEL", "WOLFRAM_KERNEL_PATH"):
        value = os.getenv(env_name)
        if value:
            return value

    candidates = WINDOWS_WOLFRAM_KERNELS + MACOS_WOLFRAM_KERNELS
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    for executable in ("wolfram", "WolframKernel", "wolframscript"):
        found = shutil.which(executable)
        if found:
            return found

    if platform.system() == "Darwin":
        return MACOS_WOLFRAM_KERNELS[0]
    return WINDOWS_WOLFRAM_KERNELS[0]
