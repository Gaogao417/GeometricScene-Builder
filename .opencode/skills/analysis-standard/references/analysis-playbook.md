# Analysis Playbook

## Inputs
- `results.jsonl`
- `ratings.csv`

## Merge key
`problem_id + recipe_name + seed`

## Core metrics
- `success_rate = success_count / total_count`
- `timeout_rate = timeout_count / total_count`
- `p50_solve_time`
- `p90_solve_time`
- `mean_rating`

## Pareto candidate criteria
A recipe is dominated if another recipe has:
- greater or equal mean rating, and
- less or equal mean solve time,
- with at least one strict improvement.

## Output block template
1. Top 1 recommendation
2. Two backup candidates
3. Risks (speed or stability)
4. Next sweep suggestion (which bound to tighten/relax)
