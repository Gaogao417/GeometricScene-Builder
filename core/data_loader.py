"""
Data Loader Module

从 results.jsonl、problems.jsonl、ratings.csv 加载数据，返回 pandas DataFrame。
供 analyst-reporter 和其他分析模块使用。
"""

import json
import warnings
from pathlib import Path
from typing import Union

import pandas as pd


def _resolve_run_dir(run_dir: Union[Path, str]) -> Path:
    """Resolve and validate run directory."""
    run_dir = Path(run_dir)
    if not run_dir.is_absolute():
        from pathlib import Path as _P

        run_dir = _P.cwd() / run_dir
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")
    return run_dir


def load_results(run_dir: Union[Path, str]) -> pd.DataFrame:
    """
    Load benchmark results from run_dir/results.jsonl.

    Parameters
    ----------
    run_dir : Path | str
        Run directory path (e.g., outputs/run_001)

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: problem_id, recipe_name, seed, success,
        solve_time_s, fail_type, scene_build_time_s, solver_wall_time_s,
        parameters, algebraic_complexity, image_path, geometric_scene_code
    """
    run_dir = _resolve_run_dir(run_dir)
    results_path = run_dir / "results.jsonl"

    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")

    records = []
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    return df


def load_problems(run_dir: Union[Path, str]) -> pd.DataFrame:
    """
    Load problem definitions from run_dir/inputs/problems.jsonl.

    Parameters
    ----------
    run_dir : Path | str
        Run directory path

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: id, points, base_edge, base_hypotheses_wl,
        text, constructed_points, meta
    """
    run_dir = _resolve_run_dir(run_dir)
    problems_path = run_dir / "inputs" / "problems.jsonl"

    if not problems_path.exists():
        problems_path = run_dir / "problems.jsonl"

    if not problems_path.exists():
        raise FileNotFoundError(f"Problems file not found: {problems_path}")

    records = []
    with open(problems_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    return df


def load_ratings(run_dir: Union[Path, str]) -> pd.DataFrame:
    """
    Load human ratings from run_dir/ratings.csv.

    Parameters
    ----------
    run_dir : Path | str
        Run directory path

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: problem_id, recipe_name, seed, rating,
        comment, rated_at. Returns empty DataFrame if file not found.
    """
    run_dir = _resolve_run_dir(run_dir)
    ratings_path = run_dir / "ratings.csv"

    if not ratings_path.exists():
        warnings.warn(f"Ratings file not found: {ratings_path}", UserWarning)
        return pd.DataFrame(
            columns=[
                "problem_id",
                "recipe_name",
                "seed",
                "rating",
                "comment",
                "rated_at",
            ]
        )

    df = pd.read_csv(ratings_path)
    return df


def merge_all(run_dir: Union[Path, str]) -> pd.DataFrame:
    """
    Merge results, problems, and ratings into a single DataFrame.

    Join keys: (problem_id, recipe_name, seed)

    Parameters
    ----------
    run_dir : Path | str
        Run directory path

    Returns
    -------
    pd.DataFrame
        Merged DataFrame with all columns from all sources.
        Problems are joined on problem_id (results.problem_id = problems.id).
    """
    results_df = load_results(run_dir)
    problems_df = load_problems(run_dir)
    ratings_df = load_ratings(run_dir)

    if results_df.empty:
        return pd.DataFrame()

    merged = results_df.copy()

    if not problems_df.empty:
        problems_renamed = problems_df.rename(columns={"id": "problem_id"})
        merged = merged.merge(
            problems_renamed,
            on="problem_id",
            how="left",
            suffixes=("", "_problem"),
        )

    if not ratings_df.empty:
        merge_keys = ["problem_id", "recipe_name", "seed"]
        ratings_subset = ratings_df[
            [
                c
                for c in ratings_df.columns
                if c in merge_keys or c not in merged.columns
            ]
        ]
        merged = merged.merge(
            ratings_subset,
            on=merge_keys,
            how="left",
            suffixes=("", "_rating"),
        )

    return merged


def get_failed_cases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter failed cases from DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame from merge_all() or load_results()

    Returns
    -------
    pd.DataFrame
        DataFrame with success == False, with fail_type distribution info.
    """
    if df.empty or "success" not in df.columns:
        return pd.DataFrame()

    failed = df[~df["success"]].copy()
    return failed


def get_low_score_cases(df: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    """
    Filter low-score cases from DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame from merge_all() with rating column
    threshold : float
        Rating threshold (default 2.0)

    Returns
    -------
    pd.DataFrame
        DataFrame with rating < threshold, excluding NaN ratings.
    """
    if df.empty or "rating" not in df.columns:
        return pd.DataFrame()

    low_score = df[df["rating"].notna() & (df["rating"] < threshold)].copy()
    return low_score


def summarize_by_recipe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize statistics grouped by recipe_name.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame from merge_all()

    Returns
    -------
    pd.DataFrame
        Grouped summary with columns:
        - count: total cases
        - success_rate: fraction of successful cases
        - mean_solve_time: average solve time (successful only)
        - mean_rating: average human rating (rated cases only)
    """
    if df.empty or "recipe_name" not in df.columns:
        return pd.DataFrame()

    def calc_stats(group):
        total = len(group)
        success_count = group["success"].sum() if "success" in group.columns else 0
        success_rate = success_count / total if total > 0 else 0.0

        successful = group[group["success"]] if "success" in group.columns else group
        mean_solve_time = (
            successful["solve_time_s"].mean()
            if "solve_time_s" in successful.columns
            else None
        )

        rated = group[group["rating"].notna()] if "rating" in group.columns else group
        mean_rating = (
            rated["rating"].mean()
            if len(rated) > 0 and "rating" in rated.columns
            else None
        )

        return pd.Series(
            {
                "count": total,
                "success_rate": success_rate,
                "mean_solve_time": mean_solve_time,
                "mean_rating": mean_rating,
            }
        )

    summary = df.groupby("recipe_name").apply(calc_stats, include_groups=False)
    return summary.reset_index()
