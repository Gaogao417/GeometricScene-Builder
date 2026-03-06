#!/usr/bin/env python3
"""Check data quality issues in the analysis report."""

import json
import pandas as pd
import sys

# Force UTF-8 output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    # Load results
    results = []
    with open("outputs/run_20260225_090202/results.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))

    df = pd.DataFrame(results)

    # Add problem type column
    df["problem_type"] = df["problem_id"].apply(
        lambda x: "angle_bisector" if "jiao_ping_fen" in x else "bei_zhang_zhong_xian"
    )

    print("=" * 60)
    print("PROBLEM 1: Are failed cases filtered in time calculation?")
    print("=" * 60)
    print()

    all_mean = df["solve_time_s"].mean()
    success_mean = df[df["success"]]["solve_time_s"].mean()

    print(f"All cases mean solve_time_s: {all_mean:.4f}s")
    print(f"Success only mean solve_time_s: {success_mean:.4f}s")
    print(f"Difference: {all_mean - success_mean:.4f}s")
    print()

    # Check failed cases
    failed = df[~df["success"]]
    print(f"Failed cases count: {len(failed)}")
    print()
    print("Failed cases with solve_time_s > 0:")
    failed_with_time = failed[failed["solve_time_s"] > 0]
    print(
        failed_with_time[
            ["problem_id", "recipe_name", "seed", "solve_time_s", "fail_type"]
        ].to_string()
    )
    print()

    # Compare report values vs correct values
    print("REPORT VALUES (potentially incorrect - may include failed cases):")
    print("-" * 60)
    for recipe in sorted(df["recipe_name"].unique()):
        subset = df[df["recipe_name"] == recipe]
        if len(subset) > 0:
            print(
                f"  {recipe}: mean={subset['solve_time_s'].mean():.4f}s (N={len(subset)})"
            )

    print()
    print("CORRECT VALUES (success only):")
    print("-" * 60)
    for recipe in sorted(df["recipe_name"].unique()):
        subset = df[(df["recipe_name"] == recipe) & (df["success"])]
        if len(subset) > 0:
            print(
                f"  {recipe}: mean={subset['solve_time_s'].mean():.4f}s (N={len(subset)})"
            )

    print()
    print("=" * 60)
    print("PROBLEM 2: Cross-analysis by problem type x constraint type")
    print("=" * 60)
    print()

    # Problem type counts
    print("Problem type distribution:")
    print(df["problem_type"].value_counts())
    print()

    # Cross-tabulation
    print("Success rate by problem type x constraint type:")
    print("-" * 60)

    success_pivot = (
        df.pivot_table(
            index="problem_type",
            columns="recipe_name",
            values="success",
            aggfunc="mean",
        )
        * 100
    )

    print(success_pivot.round(1).to_string())
    print()

    print("Mean solve time (success only) by problem type x constraint type:")
    print("-" * 60)

    # Filter success cases only for time calculation
    success_df = df[df["success"]]
    time_pivot = success_df.pivot_table(
        index="problem_type",
        columns="recipe_name",
        values="solve_time_s",
        aggfunc="mean",
    )

    print(time_pivot.round(3).to_string())
    print()

    # Recommendation
    print("=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print()

    for problem_type in ["bei_zhang_zhong_xian", "angle_bisector"]:
        print(f"For {problem_type}:")
        subset = df[df["problem_type"] == problem_type]

        # Find best recipe by success rate
        success_rates = subset.groupby("recipe_name")["success"].agg(["mean", "count"])
        success_rates.columns = ["success_rate", "total"]

        # Find best by time (success only)
        time_stats = (
            subset[subset["success"]]
            .groupby("recipe_name")["solve_time_s"]
            .agg(["mean", "count"])
        )
        time_stats.columns = ["mean_time", "success_count"]

        combined = success_rates.join(time_stats)
        combined = combined.sort_values("success_rate", ascending=False)

        print(combined.round(3).to_string())
        print()

        best_recipe = combined.index[0]
        best_rate = combined.loc[best_recipe, "success_rate"]
        best_time = combined.loc[best_recipe, "mean_time"]

        print(f"  Best constraint: {best_recipe}")
        print(f"  - Success rate: {best_rate * 100:.1f}%")
        print(f"  - Mean time: {best_time:.3f}s")
        print()


if __name__ == "__main__":
    main()
