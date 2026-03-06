#!/usr/bin/env python3
"""
Analyze benchmark results and generate statistical report
Usage: python analyze.py --run_dir <run_directory>
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

try:
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError as e:
    print(
        json.dumps({"status": "error", "message": f"Missing plotting libraries: {e}"})
    )
    sys.exit(1)


def load_results(run_dir: Path) -> List[Dict]:
    """Load results from results.jsonl."""
    results_path = run_dir / "results.jsonl"
    results = []
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def load_ratings(run_dir: Path) -> Dict[str, Dict]:
    """Load human ratings from ratings.csv if exists."""
    ratings_path = run_dir / "ratings.csv"
    ratings = {}
    if ratings_path.exists():
        df = pd.read_csv(ratings_path)
        for _, row in df.iterrows():
            key = f"{row['problem_id']}_{row['seed']}"
            ratings[key] = dict(row)
    return ratings


def generate_analysis(results: List[Dict], ratings: Dict, run_dir: Path) -> str:
    """Generate markdown analysis report."""
    df = pd.DataFrame(results)

    # Merge with ratings (only if ratings exist)
    df["key"] = df["problem_id"] + "_" + df["seed"].astype(str)
    if ratings:
        ratings_df = pd.DataFrame(list(ratings.values()))
        if "key" in ratings_df.columns:
            df = df.merge(ratings_df, on="key", how="left", suffixes=("", "_rating"))

    md = f"""# Benchmark Analysis Report

**Run Directory:** {run_dir}

## Summary Statistics

- **Total Cases:** {len(df)}
- **Successful:** {df["success"].sum()}
- **Success Rate:** {df["success"].mean() * 100:.1f}%
- **Median Solve Time (successful):** {df[df["success"]]["solve_time_s"].median():.2f}s
- **P90 Solve Time (successful):** {df[df["success"]]["solve_time_s"].quantile(0.9):.2f}s
"""

    if "rating" in df.columns and df["rating"].notna().any():
        avg_rating = df["rating"].mean()
        md += f"- **Average Human Rating:** {avg_rating:.2f} / 5.00\n"

    md += "\n## By Recipe\n\n"

    # Group by recipe
    recipe_stats = (
        df.groupby("recipe_name")
        .agg({"success": ["count", "sum"], "solve_time_s": ["mean", "median"]})
        .round(2)
    )

    recipe_stats.columns = ["total", "successful", "mean_time", "median_time"]
    recipe_stats["success_rate"] = (
        recipe_stats["successful"] / recipe_stats["total"] * 100
    ).round(1)

    md += "| Recipe | Total | Success | Success Rate | Mean Time | Median Time |\n"
    md += "|--------|-------|---------|--------------|-----------|------------|\n"

    for recipe, row in recipe_stats.iterrows():
        md += f"| {recipe} | {int(row['total'])} | {int(row['successful'])} | {row['success_rate']}% | {row['mean_time']}s | {row['median_time']}s |\n"

    md += "\n## Failure Analysis\n\n"

    failures = df[~df["success"]]
    if len(failures) > 0:
        fail_counts = failures["fail_type"].value_counts()
        md += "| Fail Type | Count | Percentage |\n"
        md += "|-----------|-------|------------|\n"
        for fail_type, count in fail_counts.items():
            pct = count / len(failures) * 100
            md += f"| {fail_type} | {count} | {pct:.1f}% |\n"
    else:
        md += "No failures.\n"

    return md


def generate_figures(results: List[Dict], ratings: Dict, run_dir: Path):
    """Generate interactive plotly figures."""
    df = pd.DataFrame(results)
    df["key"] = df["problem_id"] + "_" + df["seed"].astype(str)
    df = df.merge(
        pd.DataFrame(list(ratings.values())),
        on="key",
        how="left",
        suffixes=("", "_rating"),
    )

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(exist_ok=True)

    # Figure 1: Success rate by recipe
    success_rate = (
        df.groupby("recipe_name").agg({"success": ["count", "sum"]}).reset_index()
    )
    success_rate.columns = ["recipe", "total", "successful"]
    success_rate["rate"] = success_rate["successful"] / success_rate["total"] * 100

    fig1 = px.bar(
        success_rate,
        x="recipe",
        y="rate",
        title="Success Rate by Recipe",
        labels={"rate": "Success Rate (%)", "recipe": "Constraint Recipe"},
    )
    fig1.write_html(figures_dir / "success_rate.html")

    # Figure 2: Solve time distribution by recipe
    fig2 = px.box(
        df[df["success"]],
        x="recipe_name",
        y="solve_time_s",
        title="Solve Time Distribution (Successful Cases)",
        labels={"solve_time_s": "Time (s)", "recipe_name": "Constraint Recipe"},
    )
    fig2.write_html(figures_dir / "solve_time.html")

    # Figure 3: Rating vs Time (if ratings exist)
    if "rating" in df.columns and df["rating"].notna().any():
        rated = df[df["rating"].notna()]
        fig3 = px.scatter(
            rated,
            x="solve_time_s",
            y="rating",
            color="recipe_name",
            title="Rating vs Solve Time",
            labels={"solve_time_s": "Time (s)", "rating": "Rating (1-5)"},
        )
        fig3.write_html(figures_dir / "rating_vs_time.html")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze benchmark results")
    parser.add_argument("--run_dir", required=True, help="Run directory path")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)

    if not run_dir.exists():
        print(
            json.dumps(
                {"status": "error", "message": f"Run directory not found: {run_dir}"}
            )
        )
        sys.exit(1)

    # Load data
    results = load_results(run_dir)
    ratings = load_ratings(run_dir)

    # Generate analysis
    analysis_md = generate_analysis(results, ratings, run_dir)

    # Save analysis
    analysis_path = run_dir / "analysis.md"
    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write(analysis_md)

    # Generate figures
    try:
        generate_figures(results, ratings, run_dir)
    except Exception as e:
        print(f"Warning: Failed to generate figures: {e}", file=sys.stderr)

    print(f"Analysis saved to {analysis_path}")

    # Output JSON result
    print(json.dumps({"status": "ok", "analysis": str(analysis_path)}))


if __name__ == "__main__":
    main()
