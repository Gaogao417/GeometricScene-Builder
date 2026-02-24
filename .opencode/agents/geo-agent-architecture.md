# Geo Agents Overview

This folder defines one prime agent and four subagents for the geometry benchmark workflow.

## Agents
- `geo-orchestrator`: Prime agent and only user-facing entry.
- `problem-constraint-designer`: Build problem set and sweep recipes.
- `bench-runner`: Execute benchmark and generate artifacts.
- `scorer-ui`: Launch and manage manual scoring loop.
- `analyst-reporter`: Merge metrics and ratings, then output final recommendation.

## Required run order
1. `problem-constraint-designer`
2. `bench-runner`
3. `scorer-ui` (skip if no manual scoring)
4. `analyst-reporter`

## Skills bound to this architecture
- `dimensionless-constraints-library`
- `wl-benchmark-runbook`
- `human-rating-loop`
- `reporting-standard`
- `analysis-standard`

## Custom tools bound to this architecture
- `run_sweep(config_path, out_dir?, problems_path?)`
- `launch_rater(run_dir)`
- `build_report(run_dir)`

## Shared handoff contract
Each agent must write machine-readable artifacts and return exact paths.

```json
{
  "status": "ok",
  "artifacts": {
    "primary": "outputs/run_YYYYMMDD_HHMM/results.jsonl"
  },
  "next_agent": "scorer-ui"
}
```

If a step fails, return:

```json
{
  "status": "error",
  "reason": "timeout",
  "action": "lower constraints or increase timeout"
}
```
