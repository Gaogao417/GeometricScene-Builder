#!/usr/bin/env python3
"""
Generate MD and HTML reports from benchmark results
Usage: python report.py --run_dir <run_directory>
"""

import json
import sys
from pathlib import Path
from typing import List, Dict
import base64


def load_results(run_dir: Path) -> List[Dict]:
    """Load results from results.jsonl."""
    results_path = run_dir / "results.jsonl"
    results = []
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def image_to_base64(img_path: Path) -> str:
    """Convert image to base64 for HTML embedding."""
    if not img_path.exists():
        return ""
    with open(img_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def generate_markdown(results: List[Dict], run_dir: Path) -> str:
    """Generate markdown report."""
    md = f"""# Geometric Scene Benchmark Report

**Run Directory:** {run_dir}
**Total Cases:** {len(results)}
**Successful:** {sum(1 for r in results if r.get("success"))}

## Results Table

| Problem ID | Recipe | Seed | Success | Time (s) | Fail Type | Image |
|------------|---------|-------|---------|-----------|-----------|--------|
"""

    for r in results:
        problem_id = r.get("problem_id", "N/A")
        recipe = r.get("recipe_name", "N/A")
        seed = r.get("seed", "N/A")
        success = r.get("success", False)
        time_s = r.get("solve_time_s", "N/A")
        fail_type = r.get("fail_type", "")
        image_path = r.get("image_path", "")

        success_mark = "✓" if success else "✗"
        fail_str = fail_type if not success else ""

        if image_path:
            # image_path is relative to run_dir, use it directly
            img_link = f"![img]({image_path})"
        else:
            img_link = "-"

        md += f"| {problem_id} | {recipe} | {seed} | {success_mark} {time_s} | {fail_str} | {img_link} |\n"

    return md


def generate_html(results: List[Dict], run_dir: Path) -> str:
    """Generate HTML report."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Geometric Scene Benchmark Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .success {{ color: green; font-weight: bold; }}
        .fail {{ color: red; font-weight: bold; }}
        .thumbnail {{ max-width: 100px; height: auto; }}
    </style>
</head>
<body>
    <h1>Geometric Scene Benchmark Report</h1>
    <p><strong>Run Directory:</strong> {run_dir}</p>
    <p><strong>Total Cases:</strong> {len(results)}</p>
    <p><strong>Successful:</strong> {sum(1 for r in results if r.get("success"))}</p>

    <h2>Results Table</h2>
    <table>
        <thead>
            <tr>
                <th>Problem ID</th>
                <th>Recipe</th>
                <th>Seed</th>
                <th>Success</th>
                <th>Time (s)</th>
                <th>Fail Type</th>
                <th>Image</th>
            </tr>
        </thead>
        <tbody>
"""

    for r in results:
        problem_id = r.get("problem_id", "N/A")
        recipe = r.get("recipe_name", "N/A")
        seed = r.get("seed", "N/A")
        success = r.get("success", False)
        time_s = r.get("solve_time_s", "N/A")
        fail_type = r.get("fail_type", "")
        image_path = r.get("image_path", "")

        success_class = "success" if success else "fail"
        success_mark = "✓" if success else "✗"
        fail_str = fail_type if not success else "-"

        img_html = "-"
        if image_path and (run_dir / image_path).exists():
            img_data = image_to_base64(run_dir / image_path)
            img_html = f'<img src="data:image/png;base64,{img_data}" class="thumbnail" alt="scene image">'

        html += f"""
            <tr>
                <td>{problem_id}</td>
                <td>{recipe}</td>
                <td>{seed}</td>
                <td class="{success_class}">{success_mark}</td>
                <td>{time_s}</td>
                <td>{fail_str}</td>
                <td>{img_html}</td>
            </tr>
"""

    html += """
        </tbody>
    </table>
</body>
</html>
"""

    return html


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate benchmark reports")
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

    results_path = run_dir / "results.jsonl"
    if not results_path.exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": f"Results file not found: {results_path}",
                }
            )
        )
        sys.exit(1)

    # Load results
    results = load_results(run_dir)

    # Generate reports
    md = generate_markdown(results, run_dir)
    html = generate_html(results, run_dir)

    # Save reports
    md_path = run_dir / "report.md"
    html_path = run_dir / "report.html"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Reports generated:")
    print(f"  Markdown: {md_path}")
    print(f"  HTML: {html_path}")

    # Output JSON result
    print(json.dumps({"status": "ok", "report": str(md_path), "html": str(html_path)}))


if __name__ == "__main__":
    main()
