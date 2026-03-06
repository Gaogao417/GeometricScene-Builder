#!/usr/bin/env python3
"""
按具体问题ID分析约束对效率的影响
"""

import json
from collections import defaultdict
from pathlib import Path


def load_results(results_path: str) -> list[dict]:
    """加载 results.jsonl 文件"""
    results = []
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def analyze_by_problem(results: list[dict]) -> dict:
    """
    按问题ID和约束名称分析
    返回: {problem_id: {recipe_name: {success_count, total_count, success_times}}}
    """
    analysis = defaultdict(
        lambda: defaultdict(
            lambda: {"success_count": 0, "total_count": 0, "success_times": []}
        )
    )

    for record in results:
        problem_id = record["problem_id"]
        recipe_name = record["recipe_name"]
        success = record.get("success", False)
        solve_time = record.get("solve_time_s", 0)

        analysis[problem_id][recipe_name]["total_count"] += 1
        if success:
            analysis[problem_id][recipe_name]["success_count"] += 1
            analysis[problem_id][recipe_name]["success_times"].append(solve_time)

    return analysis


def get_recipe_short_name(recipe_name: str) -> str:
    """获取约束的简短名称"""
    mapping = {
        "baseline": "baseline",
        "constraint_1a_horizontal": "1a_h",
        "constraint_1b_clockwise": "1b_c",
        "constraint_1c_region": "1c_r",
        "constraint_2a_horizontal_clockwise": "2a_hc",
        "constraint_2b_horizontal_region": "2b_hr",
        "constraint_2c_clockwise_region": "2c_cr",
    }
    return mapping.get(recipe_name, recipe_name)


def get_avg_time(times: list[float]) -> float:
    """计算平均时间"""
    if not times:
        return float("inf")
    return sum(times) / len(times)


def find_best_recipe(problem_data: dict) -> tuple[str, int, float]:
    """
    找到最优约束
    优先级：成功率最高 > 平均时间最短
    返回: (recipe_name, success_count, avg_time)
    """
    best = None
    best_success = -1
    best_time = float("inf")

    for recipe, data in problem_data.items():
        success_count = data["success_count"]
        avg_time = get_avg_time(data["success_times"])

        # 优先比较成功率
        if success_count > best_success:
            best = recipe
            best_success = success_count
            best_time = avg_time
        elif success_count == best_success and avg_time < best_time:
            best = recipe
            best_time = avg_time

    return best, best_success, best_time


def format_cell(data: dict) -> str:
    """格式化单元格：成功率/平均时间"""
    success_count = data["success_count"]
    total_count = data["total_count"]
    times = data["success_times"]

    if success_count == 0:
        return "0/-"

    avg_time = get_avg_time(times)
    return f"{success_count}/{avg_time:.1f}s"


def generate_markdown_report(analysis: dict, output_path: str):
    """生成Markdown报告"""
    # 定义约束顺序
    recipe_order = [
        "baseline",
        "constraint_1a_horizontal",
        "constraint_1b_clockwise",
        "constraint_1c_region",
        "constraint_2a_horizontal_clockwise",
        "constraint_2b_horizontal_region",
        "constraint_2c_clockwise_region",
    ]

    # 按问题ID排序
    problem_ids = sorted(analysis.keys())

    # 收集统计数据
    efficiency_improvements = []  # (problem_id, recipe, baseline_time, recipe_time, improvement_pct)
    no_change_problems = []
    slower_problems = []  # (problem_id, recipe, baseline_time, recipe_time, slowdown_pct)

    lines = []
    lines.append("## 按问题的约束效率矩阵\n")
    lines.append(
        "| 问题ID | baseline | 1a_h | 1b_c | 1c_r | 2a_hc | 2b_hr | 2c_cr | 最优约束 |"
    )
    lines.append(
        "|--------|----------|------|------|------|-------|-------|-------|----------|"
    )

    for problem_id in problem_ids:
        problem_data = analysis[problem_id]

        # 找最优约束
        best_recipe, best_success, best_time = find_best_recipe(problem_data)
        best_short = get_recipe_short_name(best_recipe)

        # 获取baseline数据用于比较
        baseline_data = problem_data.get("baseline", {"success_times": []})
        baseline_avg = (
            get_avg_time(baseline_data["success_times"])
            if baseline_data["success_times"]
            else float("inf")
        )

        row = [problem_id]
        for recipe in recipe_order:
            if recipe in problem_data:
                cell = format_cell(problem_data[recipe])
                row.append(cell)

                # 计算效率变化
                if recipe != "baseline" and baseline_avg != float("inf"):
                    recipe_avg = (
                        get_avg_time(problem_data[recipe]["success_times"])
                        if problem_data[recipe]["success_times"]
                        else float("inf")
                    )
                    if recipe_avg != float("inf"):
                        improvement = (baseline_avg - recipe_avg) / baseline_avg * 100
                        if improvement > 20:
                            efficiency_improvements.append(
                                (
                                    problem_id,
                                    recipe,
                                    baseline_avg,
                                    recipe_avg,
                                    improvement,
                                )
                            )
                        elif improvement < -20:
                            slower_problems.append(
                                (
                                    problem_id,
                                    recipe,
                                    baseline_avg,
                                    recipe_avg,
                                    -improvement,
                                )
                            )
            else:
                row.append("-")

        row.append(best_short)
        lines.append("| " + " | ".join(row) + " |")

    # 关键发现部分
    lines.append("\n## 关键发现\n")

    # 效率提升最大的问题
    lines.append("### 效率提升最大的问题 (>20%)\n")
    if efficiency_improvements:
        efficiency_improvements.sort(key=lambda x: x[4], reverse=True)
        for (
            problem_id,
            recipe,
            baseline_t,
            recipe_t,
            improvement,
        ) in efficiency_improvements[:15]:
            recipe_short = get_recipe_short_name(recipe)
            lines.append(
                f"- **{problem_id}**: {recipe_short} 比 baseline 快 {improvement:.0f}% ({baseline_t:.2f}s → {recipe_t:.2f}s)"
            )
    else:
        lines.append("- 无明显效率提升的问题")

    # 约束反而变慢的问题
    lines.append("\n### 约束反而变慢的问题 (>20%)\n")
    if slower_problems:
        slower_problems.sort(key=lambda x: x[4], reverse=True)
        for problem_id, recipe, baseline_t, recipe_t, slowdown in slower_problems[:15]:
            recipe_short = get_recipe_short_name(recipe)
            lines.append(
                f"- **{problem_id}**: {recipe_short} 比 baseline 慢 {slowdown:.0f}% ({baseline_t:.2f}s → {recipe_t:.2f}s)"
            )
    else:
        lines.append("- 无明显变慢的问题")

    # 统计摘要
    lines.append("\n### 统计摘要\n")

    # 最优约束分布
    best_count = defaultdict(int)
    for problem_id in problem_ids:
        problem_data = analysis[problem_id]
        best_recipe, _, _ = find_best_recipe(problem_data)
        best_count[get_recipe_short_name(best_recipe)] += 1

    lines.append("**最优约束分布**:")
    for recipe_short in ["baseline", "1a_h", "1b_c", "1c_r", "2a_hc", "2b_hr", "2c_cr"]:
        count = best_count.get(recipe_short, 0)
        if count > 0:
            lines.append(f"- {recipe_short}: {count} 个问题")

    # 全部成功的问题
    all_success_problems = []
    partial_success_problems = []
    for problem_id in problem_ids:
        problem_data = analysis[problem_id]
        all_success = all(
            data["success_count"] == data["total_count"]
            for data in problem_data.values()
        )
        if all_success:
            all_success_problems.append(problem_id)
        else:
            partial_success_problems.append(problem_id)

    lines.append(f"\n**全部约束都成功的问题**: {len(all_success_problems)} 个")
    if partial_success_problems:
        lines.append(f"**存在失败约束的问题**: {len(partial_success_problems)} 个")

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return lines


def main():
    results_path = "outputs/run_20260225_090202/results.jsonl"
    output_path = "outputs/run_20260225_090202/problem_constraint_matrix.md"

    print(f"Loading results from {results_path}...")
    results = load_results(results_path)
    print(f"Loaded {len(results)} records")

    print("Analyzing by problem...")
    analysis = analyze_by_problem(results)
    print(f"Found {len(analysis)} unique problems")

    print(f"Generating report to {output_path}...")
    generate_markdown_report(analysis, output_path)
    print("Done!")

    # 打印问题ID列表
    print("\n问题ID列表:")
    for pid in sorted(analysis.keys()):
        print(f"  - {pid}")


if __name__ == "__main__":
    main()
