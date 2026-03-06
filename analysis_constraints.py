import json
from collections import defaultdict
import statistics

# 读取数据
data = []
with open("outputs/run_20260225_090202/results.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        data.append(json.loads(line.strip()))

# 筛选成功案例
success_data = [d for d in data if d.get("success") == True]
print(f"总记录数: {len(data)}")
print(f"成功案例数: {len(success_data)}")

# 1. 按约束类型统计
recipe_times = defaultdict(list)
for d in success_data:
    recipe_times[d["recipe_name"]].append(d["solve_time_s"])

print("\n### 1. 按约束类型的运行时间")
print()
print("| 约束类型 | 成功数 | 平均时间 | 标准差 | 中位数 | 最小 | 最大 |")
print("|----------|--------|----------|--------|--------|------|------|")

recipe_stats = {}
for recipe, times in sorted(recipe_times.items()):
    mean_t = statistics.mean(times)
    std_t = statistics.stdev(times) if len(times) > 1 else 0
    median_t = statistics.median(times)
    min_t = min(times)
    max_t = max(times)
    recipe_stats[recipe] = {
        "n": len(times),
        "mean": mean_t,
        "std": std_t,
        "median": median_t,
        "min": min_t,
        "max": max_t,
    }
    print(
        f"| {recipe} | {len(times)} | {mean_t:.2f}s | {std_t:.2f}s | {median_t:.2f}s | {min_t:.2f}s | {max_t:.2f}s |"
    )

# 2. 按约束数量分类
constraint_0 = ["baseline"]
constraint_1 = [
    "constraint_1a_horizontal",
    "constraint_1b_clockwise",
    "constraint_1c_region",
]
constraint_2 = [
    "constraint_2a_horizontal_clockwise",
    "constraint_2b_horizontal_region",
    "constraint_2c_clockwise_region",
]


def get_group_stats(recipes):
    times = []
    for r in recipes:
        times.extend(recipe_times.get(r, []))
    if not times:
        return {"n": 0, "mean": 0, "median": 0}
    return {
        "n": len(times),
        "mean": statistics.mean(times),
        "median": statistics.median(times),
    }


stats_0 = get_group_stats(constraint_0)
stats_1 = get_group_stats(constraint_1)
stats_2 = get_group_stats(constraint_2)

baseline_mean = stats_0["mean"]

print()
print("### 2. 按约束数量的运行时间")
print()
print("| 约束数量 | 成功数 | 平均时间 | 中位数 | 相对 baseline |")
print("|----------|--------|----------|--------|---------------|")

rel_1 = (
    ((stats_1["mean"] - baseline_mean) / baseline_mean * 100)
    if baseline_mean > 0
    else 0
)
rel_2 = (
    ((stats_2["mean"] - baseline_mean) / baseline_mean * 100)
    if baseline_mean > 0
    else 0
)

print(
    f"| 0约束 (baseline) | {stats_0['n']} | {stats_0['mean']:.2f}s | {stats_0['median']:.2f}s | 基准 |"
)
print(
    f"| 1约束 | {stats_1['n']} | {stats_1['mean']:.2f}s | {stats_1['median']:.2f}s | {rel_1:+.1f}% |"
)
print(
    f"| 2约束 | {stats_2['n']} | {stats_2['mean']:.2f}s | {stats_2['median']:.2f}s | {rel_2:+.1f}% |"
)

# 3. 效率排行
print()
print("### 3. 效率排行（从快到慢）")
print()
sorted_recipes = sorted(recipe_stats.items(), key=lambda x: x[1]["mean"])
for i, (recipe, stats) in enumerate(sorted_recipes, 1):
    print(
        f"{i}. {recipe}: {stats['mean']:.2f}s (N={stats['n']}, 中位数={stats['median']:.2f}s)"
    )

# 4. 置信区间分析
print()
print("### 4. 统计显著性分析（95%置信区间近似）")
print()
print("| 约束类型 | 平均时间 | 标准误差(SE) | 95% CI 下界 | 95% CI 上界 |")
print("|----------|----------|--------------|-------------|-------------|")

for recipe, stats in sorted(recipe_stats.items(), key=lambda x: x[1]["mean"]):
    se = stats["std"] / (stats["n"] ** 0.5) if stats["n"] > 1 else 0
    ci_low = stats["mean"] - 1.96 * se
    ci_high = stats["mean"] + 1.96 * se
    print(
        f"| {recipe} | {stats['mean']:.2f}s | {se:.3f}s | {ci_low:.2f}s | {ci_high:.2f}s |"
    )

# 5. 结论
print()
print("### 5. 结论")
print()
fastest = sorted_recipes[0]
slowest = sorted_recipes[-1]
print(f"- **最快的约束**: {fastest[0]} (平均 {fastest[1]['mean']:.2f}s)")
print(f"- **最慢的约束**: {slowest[0]} (平均 {slowest[1]['mean']:.2f}s)")
print(
    f"- **约束是否加速求解**: 1约束平均 {stats_1['mean']:.2f}s, 2约束平均 {stats_2['mean']:.2f}s, baseline {stats_0['mean']:.2f}s"
)

# 检查置信区间是否重叠
baseline_se = (
    recipe_stats["baseline"]["std"] / (recipe_stats["baseline"]["n"] ** 0.5)
    if recipe_stats["baseline"]["n"] > 1
    else 0
)
baseline_ci = (
    stats_0["mean"] - 1.96 * baseline_se,
    stats_0["mean"] + 1.96 * baseline_se,
)

print()
print("**显著性分析**:")
for recipe, stats in sorted_recipes:
    if recipe == "baseline":
        continue
    se = stats["std"] / (stats["n"] ** 0.5) if stats["n"] > 1 else 0
    ci = (stats["mean"] - 1.96 * se, stats["mean"] + 1.96 * se)
    overlaps = not (ci[1] < baseline_ci[0] or ci[0] > baseline_ci[1])
    sig = "无显著差异" if overlaps else "有显著差异"
    print(
        f"- {recipe}: CI [{ci[0]:.2f}, {ci[1]:.2f}] vs baseline [{baseline_ci[0]:.2f}, {baseline_ci[1]:.2f}] -> {sig}"
    )
