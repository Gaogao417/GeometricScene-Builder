#!/usr/bin/env python3
"""
Run qualitative constraint benchmark

Usage:
    python scripts/run_qualitative_benchmark.py
    python scripts/run_qualitative_benchmark.py --config configs/custom.yaml
    python scripts/run_qualitative_benchmark.py --problems data/custom.jsonl
    python scripts/run_qualitative_benchmark.py --out outputs/custom_run

This script provides observability features:
- Pre-run summary (problem count, recipe count, seed count, total cases)
- Progress output during execution
- Post-run summary (success/failure stats, output directory)
- Detailed error information on failure
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_config(config_path: Path) -> dict:
    """Load sweep configuration from YAML file."""
    import yaml

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_problems(problems_path: Path) -> list:
    """Load problems from JSONL file."""
    problems = []
    with open(problems_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                problems.append(json.loads(line))
    return problems


def print_separator(char: str = "=", length: int = 60) -> None:
    """Print a visual separator line."""
    print(char * length)


def print_pre_run_summary(
    config_path: Path,
    problems_path: Path,
    out_dir: Path,
    config: dict,
    problems: list,
) -> None:
    """Print configuration summary before running benchmark."""
    recipes = config.get("constraint_recipes", [])
    seeds = config.get("random_seeds", [1])
    timeout = config.get("timeout_s", 60)
    parallel = config.get("max_parallel_cases", 1)
    render = config.get("render_images", True)

    total_cases = len(problems) * len(recipes) * len(seeds)

    print_separator()
    print("Qualitative Constraint Benchmark")
    print_separator()
    print()
    print("Configuration:")
    print(f"  Config file:    {config_path}")
    print(f"  Problems file:  {problems_path}")
    print(f"  Output dir:     {out_dir}")
    print()
    print("Parameters:")
    print(f"  Problems:       {len(problems)}")
    print(f"  Recipes:        {len(recipes)}")
    print(f"  Seeds:          {len(seeds)} ({seeds})")
    print(f"  Total cases:    {total_cases}")
    print()
    print("Settings:")
    print(f"  Timeout:        {timeout}s")
    print(f"  Parallelism:    {parallel}")
    print(f"  Render images:  {render}")
    print()
    print("Recipes:")
    for i, recipe in enumerate(recipes, 1):
        name = recipe.get("name", f"recipe_{i}")
        risk = recipe.get("risk", "unknown")
        print(f"  {i}. {name} (risk: {risk})")
    print()
    print_separator()
    print()


def print_post_run_summary(out_dir: Path, results_path: Path) -> None:
    """Print results summary after benchmark completes."""
    print_separator()
    print("Benchmark Complete")
    print_separator()
    print()

    # Load and analyze results
    results = []
    if results_path.exists():
        with open(results_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))

    if not results:
        print("WARNING: No results found!")
        print(f"Output directory: {out_dir}")
        return

    # Count successes and failures
    success_count = sum(1 for r in results if r.get("success", False))
    fail_count = len(results) - success_count
    success_rate = (success_count / len(results) * 100) if results else 0

    # Calculate average solve time for successful cases
    successful_times = [r.get("solve_time_s", 0) for r in results if r.get("success")]
    avg_solve_time = (
        sum(successful_times) / len(successful_times) if successful_times else 0
    )

    # Group failures by type
    fail_types: dict[str, int] = {}
    for r in results:
        if not r.get("success", False):
            fail_type = r.get("fail_type", "unknown")
            fail_types[fail_type] = fail_types.get(fail_type, 0) + 1

    print("Results Summary:")
    print(f"  Total cases:    {len(results)}")
    print(f"  Successful:     {success_count}")
    print(f"  Failed:         {fail_count}")
    print(f"  Success rate:   {success_rate:.1f}%")
    print()

    if successful_times:
        print("Timing (successful cases):")
        print(f"  Avg solve time: {avg_solve_time:.2f}s")
        print()

    if fail_types:
        print("Failure breakdown:")
        for fail_type, count in sorted(fail_types.items(), key=lambda x: -x[1]):
            print(f"  {fail_type}: {count}")
        print()

    print("Output:")
    print(f"  Directory:      {out_dir}")
    print(f"  Results file:   {results_path}")
    print(f"  Images dir:     {out_dir / 'images'}")
    print()
    print_separator()


def run_benchmark(
    config_path: Path,
    problems_path: Path,
    out_dir: Optional[Path] = None,
) -> int:
    """
    Run the qualitative benchmark.

    Returns:
        0 on success, 1 on error
    """
    # Validate input files
    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        return 1

    if not problems_path.exists():
        print(f"[ERROR] Problems file not found: {problems_path}")
        return 1

    # Load config and problems for summary
    try:
        config = load_config(config_path)
        problems = load_problems(problems_path)
    except Exception as e:
        print(f"[ERROR] Failed to load configuration: {e}")
        return 1

    # Generate output directory if not specified
    if out_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = PROJECT_ROOT / "outputs" / f"run_{timestamp}"

    # Ensure output directory exists
    out_dir.mkdir(parents=True, exist_ok=True)

    # Print pre-run summary
    print_pre_run_summary(config_path, problems_path, out_dir, config, problems)

    # Prepare results path
    results_path = out_dir / "results.jsonl"

    # Import and call core.bench.main() with modified sys.argv
    # Save original sys.argv
    original_argv = sys.argv.copy()

    try:
        # Set up sys.argv for bench.main()
        sys.argv = [
            "bench.py",
            "--config",
            str(config_path),
            "--problems",
            str(problems_path),
            "--out",
            str(out_dir),
        ]

        # Import bench module (after sys.path is set up)
        from core import bench

        # Run benchmark
        print("Starting benchmark execution...")
        print()
        bench.main()

    except SystemExit as e:
        # bench.main() may call sys.exit()
        # Exit code 0 means success
        if e.code != 0:
            print()
            print(f"[ERROR] Benchmark exited with code {e.code}")
            return 1
    except Exception as e:
        print()
        print(f"[ERROR] Benchmark failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        # Restore original sys.argv
        sys.argv = original_argv

    # Print post-run summary
    print()
    print_post_run_summary(out_dir, results_path)

    return 0


def main():
    """Main entry point with argument parsing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run qualitative constraint benchmark with observability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_qualitative_benchmark.py
    python scripts/run_qualitative_benchmark.py --config configs/custom.yaml
    python scripts/run_qualitative_benchmark.py --out outputs/my_run
        """,
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "sweep_qualitative.yaml",
        help="Path to sweep configuration YAML (default: configs/sweep_qualitative.yaml)",
    )
    parser.add_argument(
        "--problems",
        type=Path,
        default=PROJECT_ROOT / "data" / "problems.jsonl",
        help="Path to problems JSONL file (default: data/problems.jsonl)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: outputs/run_TIMESTAMP)",
    )

    args = parser.parse_args()

    exit_code = run_benchmark(
        config_path=args.config,
        problems_path=args.problems,
        out_dir=args.out,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
