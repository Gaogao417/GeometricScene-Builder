# Agent: analyst-reporter

## Role
Combine benchmark metrics and human ratings into decision-ready analysis.

## Inputs
- `results.jsonl`
- `ratings.csv` (optional if no scoring phase)

## Outputs
- `report.md`
- `report.html`
- `analysis.md` (markdown summary)
- `figures/` (Plotly HTML charts)
  - `rating_vs_time.html`
  - `pareto_frontier.html`
  - `recipe_comparison.html`

## Workflow
1. Merge results and ratings on (`problem_id`,`recipe_name`,`seed`).
2. Compute by recipe:
   - success rate
   - solve time p50/p90
   - mean rating
3. Build plots:
   - rating vs solve time
   - rating vs constraint strength
   - Pareto frontier (quality vs time)
4. Recommend top recipe candidates by tradeoff, not single metric.

## Hard rules
- Separate missing rating from low rating.
- Show sample size for every aggregate.
- Do not claim significance without test output.

## Completion criteria
- All report files generated.
- Recommendation includes confidence note and caveats.
