"""
Geo Benchmark Core Library

底层 Wolfram 几何场景生成与基准测试库。
供 Agents 和示例代码调用。
"""

from .constraints import (
    BuildOrientation,
    BuildAngleMin,
    BuildSideRatio,
    BuildHeightBase,
    BuildHeightPerimeter,
    AssembleConstraints,
)

__all__ = [
    "BuildOrientation",
    "BuildAngleMin",
    "BuildSideRatio",
    "BuildHeightBase",
    "BuildHeightPerimeter",
    "AssembleConstraints",
]
