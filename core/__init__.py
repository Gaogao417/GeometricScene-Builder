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
    # 定性约束函数
    BuildHorizontalLine,
    BuildClockwise,
    BuildCounterclockwise,
    BuildPointInPolygon,
    BuildPointInTriangle,
    AssembleQualitativeConstraints,
)
from .data_loader import (
    load_results,
    load_problems,
    load_ratings,
    merge_all,
    get_failed_cases,
    get_low_score_cases,
    summarize_by_recipe,
)

__all__ = [
    "BuildOrientation",
    "BuildAngleMin",
    "BuildSideRatio",
    "BuildHeightBase",
    "BuildHeightPerimeter",
    "AssembleConstraints",
    # 定性约束函数
    "BuildHorizontalLine",
    "BuildClockwise",
    "BuildCounterclockwise",
    "BuildPointInPolygon",
    "BuildPointInTriangle",
    "AssembleQualitativeConstraints",
    "load_results",
    "load_problems",
    "load_ratings",
    "merge_all",
    "get_failed_cases",
    "get_low_score_cases",
    "summarize_by_recipe",
]
