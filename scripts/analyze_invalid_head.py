#!/usr/bin/env python3
"""Analyze invalid_head failures from benchmark results."""

import json
import sys
from pathlib import Path
from collections import defaultdict


def main():
    results_path = Path("outputs/run_20260225_090202/results.jsonl")

    # Load all data
    data = []
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))

    print(f"Total records: {len(data)}")

    # Categorize by success/failure
    success_df = [r for r in data if r.get("success", False)]
    fail_df = [r for r in data if not r.get("success", False)]

    print(f"Success: {len(success_df)}")
    print(f"Failure: {len(fail_df)}")

    # Fail type distribution
    fail_types = defaultdict(int)
    for r in fail_df:
        ft = r.get("fail_type", "unknown")
        fail_types[ft] += 1

    print("\n=== Fail Type Distribution ===")
    for ft, cnt in sorted(fail_types.items(), key=lambda x: -x[1]):
        print(f"  {ft}: {cnt}")

    # Filter invalid_head
    invalid_head = [r for r in fail_df if r.get("fail_type") == "invalid_head"]
    print(f"\n=== Invalid Head Failures: {len(invalid_head)} ===")

    # Group by problem_id + recipe_name
    invalid_head_groups = defaultdict(list)
    for r in invalid_head:
        key = (r["problem_id"], r["recipe_name"])
        invalid_head_groups[key].append(r)

    print(f"Unique problem+recipe combinations: {len(invalid_head_groups)}")

    # Get all problem+recipe combinations
    all_combos = defaultdict(list)
    for r in data:
        key = (r["problem_id"], r["recipe_name"])
        all_combos[key].append(r)

    # For each problem, compute success rate
    problem_stats = defaultdict(
        lambda: {"success": 0, "fail": 0, "invalid_head": 0, "total": 0}
    )
    for r in data:
        pid = r["problem_id"]
        problem_stats[pid]["total"] += 1
        if r.get("success", False):
            problem_stats[pid]["success"] += 1
        else:
            problem_stats[pid]["fail"] += 1
            if r.get("fail_type") == "invalid_head":
                problem_stats[pid]["invalid_head"] += 1

    # List unique problems and recipes
    unique_problems = sorted(set(r["problem_id"] for r in data))
    unique_recipes = sorted(set(r["recipe_name"] for r in data))

    print(f"\n=== Unique Problems ({len(unique_problems)}) ===")
    for p in unique_problems:
        stats = problem_stats[p]
        success_rate = (
            stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
        )
        print(
            f"  {p}: {stats['success']}/{stats['total']} ({success_rate:.1f}%) success, {stats['invalid_head']} invalid_head"
        )

    print(f"\n=== Unique Recipes ({len(unique_recipes)}) ===")
    for r in unique_recipes:
        print(f"  {r}")

    # For each invalid_head failure, find success in baseline/horizontal
    print("\n=== Invalid Head Analysis ===")
    print(
        "| Problem ID | Failed Recipe | Fail Count | Avg Time | Problem Success Rate |"
    )
    print(
        "|------------|---------------|------------|----------|---------------------|"
    )

    for (pid, recipe), records in sorted(invalid_head_groups.items()):
        fail_count = len(records)
        avg_time = (
            sum(r.get("solve_time_s", 0) for r in records) / fail_count
            if fail_count > 0
            else 0
        )
        stats = problem_stats[pid]
        success_rate = f"{stats['success']}/{stats['total']} ({stats['success'] / stats['total'] * 100:.1f}%)"
        print(f"| {pid} | {recipe} | {fail_count} | {avg_time:.1f}s | {success_rate} |")

    # Find problems that fail for all recipes (problem itself is hard)
    print("\n=== Problems Failing All Recipes ===")
    for pid in unique_problems:
        stats = problem_stats[pid]
        if stats["success"] == 0:
            print(f"  {pid}: 0/{stats['total']} success")

    # Find most problematic recipes
    print("\n=== Recipe Failure Analysis ===")
    recipe_stats = defaultdict(
        lambda: {"success": 0, "fail": 0, "invalid_head": 0, "total": 0}
    )
    for r in data:
        rn = r["recipe_name"]
        recipe_stats[rn]["total"] += 1
        if r.get("success", False):
            recipe_stats[rn]["success"] += 1
        else:
            recipe_stats[rn]["fail"] += 1
            if r.get("fail_type") == "invalid_head":
                recipe_stats[rn]["invalid_head"] += 1

    print("| Recipe | Total | Success | Fail | Invalid Head | Success Rate |")
    print("|--------|-------|---------|------|--------------|--------------|")
    for rn in unique_recipes:
        s = recipe_stats[rn]
        rate = s["success"] / s["total"] * 100 if s["total"] > 0 else 0
        print(
            f"| {rn} | {s['total']} | {s['success']} | {s['fail']} | {s['invalid_head']} | {rate:.1f}% |"
        )

    # Show code samples for invalid_head failures
    print("\n=== Invalid Head Code Samples ===")
    for (pid, recipe), records in list(invalid_head_groups.items())[:3]:
        print(f"\n--- {pid} / {recipe} ---")
        if records:
            code = records[0].get("geometric_scene_code", "N/A")
            if code and code != "N/A":
                print(code[:500] + "..." if len(code) > 500 else code)
            else:
                print("No code available")


if __name__ == "__main__":
    main()
