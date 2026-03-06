---
name: geo-architecture
description: Use this skill when understanding or working with the geometry benchmark agent system architecture, including agent roles, workflow orchestration, and artifact contracts.
---

# Geo Architecture Overview

This skill describes the geometry benchmark agent system structure and orchestration patterns.

## Agents

### Prime Agent
- **`@geo-orchestrator`**: The only user-facing entry point. Coordinates all subagents through the canonical workflow.

### Subagents (in execution order)
1. **`@problem-constraint-designer`**: Build problem set (`problems.jsonl`) and sweep recipes (`sweep.yaml`). Validates user-provided configs against schemas.
2. **`@bench-runner`**: Execute benchmark with solve-first strategy. Generates `results.jsonl` and optional images.
3. **`@scorer-ui`**: Launch and manage manual scoring loop (optional, skip if no manual scoring needed).
4. **`@analyst-reporter`**: Merge metrics and ratings, then output final recommendations.

## Required Run Order

```
@geo-orchestrator (prime)
  ↓
@problem-constraint-designer
  ↓
@bench-runner
  ↓
@scorer-ui (optional)
  ↓
@analyst-reporter
```

## Artifact Contracts

Each agent must write machine-readable artifacts and return exact paths.

### Success Response Format
```json
{
  "status": "ok",
  "artifacts": {
    "primary": "outputs/run_YYYYMMDD_HHMM/results.jsonl"
  },
  "next_agent": "scorer-ui"
}
```

### Error Response Format
```json
{
  "status": "error",
  "reason": "timeout",
  "action": "lower constraints or increase timeout"
}
```

## Skills Bound to This Architecture

- `dimensionless-constraints-library`: Reusable constraint recipes and risk levels
- `wl-benchmark-runbook`: GeometricScene solve/run best practices
- `human-rating-loop`: 1-5 manual scoring workflow and csv schema
- `reporting-standard`: Deterministic report structure for md/html
- `analysis-standard`: Merge, aggregate, plot, and recommend

## Custom Tools Bound to This Architecture

- `run_sweep(config_path, out_dir?, problems_path?)`: Execute benchmark sweep
- `launch_rater(run_dir)`: Launch Streamlit scoring UI
- `build_report(run_dir)`: Generate report.md, report.html, and analysis_report.html

## Key Design Principles

1. **Single Entry Point**: Users only interact with `@geo-orchestrator`
2. **Machine-Readable Handoffs**: All agent outputs follow strict schemas
3. **Explicit Failure Types**: Never merge different failure reasons
4. **Deterministic Seeds**: Keep seeds identical across recipes for comparability
5. **Artifact Paths**: Always return absolute or workspace-relative paths

## Agent Invocation Syntax

When one agent needs to call another, use the `@` syntax:
- ✅ Correct: "Call `@problem-constraint-designer` to validate the config"
- ❌ Wrong: "Call `problem-constraint-designer`" or "Call problem-constraint-designer"

This syntax makes agent references explicit and machine-parseable.

## Related Skills

- `agent-io-schema`: Canonical data schemas for all agent interactions
- `problem-collector`: Normalize source questions into `problems.jsonl`
