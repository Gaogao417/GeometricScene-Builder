# Skills Index

Core skills for the final loop:
- `agent-io-schema`: **canonical data schemas for all agent interactions** (problems.jsonl, sweep.yaml, results.jsonl, ratings.csv)
- `geo-architecture`: **geometry benchmark agent system architecture** (agent roles, workflow orchestration, artifact contracts)
- `agentic-geometry-workflow`: **single-problem diagram workflow** using opencode agents, skills, tools, render/evaluate/retry logs, and a bounded retry budget.
- `dimensionless-constraints-library`: reusable constraint recipes and risk levels.
- `wl-benchmark-runbook`: GeometricScene solve/run best practices.
- `human-rating-loop`: 1-5 manual scoring workflow and csv schema.
- `analysis-standard`: merge, aggregate, plot, and recommend.
- `reporting-standard`: deterministic report structure for md/html.

Optional skill:
- `problem-collector`: normalize source questions into `problems.jsonl` when source is raw text.

Suggested execution order:
1. agent-io-schema (understand data contracts first)
2. agentic-geometry-workflow for single-problem diagram generation, or geo-architecture for benchmark runs
3. dimensionless-constraints-library
4. wl-benchmark-runbook
5. human-rating-loop
6. reporting-standard
7. analysis-standard
