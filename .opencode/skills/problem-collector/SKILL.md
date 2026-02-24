---
name: problem-collector
description: Use this skill when converting raw geometry questions (text/API/manual lists) into normalized `problems.jsonl` records for benchmark pipelines, including point sets, base hypotheses, and metadata.
---

# Problem Collector

Normalize problem inputs into one stable JSONL format.

## Workflow
1. Read raw source and assign stable `id` (`p0001`, `p0002`, ...).
2. Extract symbolic points and constructions.
3. Keep `dsl` and `base_hypotheses_wl` as primary execution fields.
4. Save one JSON object per line to `data/problems.jsonl`.

## Required fields per record
- `id`
- `text` (optional display)
- `dsl`
- `points`
- `base_hypotheses_wl`
- `meta.source`

See schema and examples in `references/problem-jsonl-schema.md`.

## Guardrails
- Keep symbol naming consistent across all recipes.
- Never mix point casing (`A` vs `a`) in one record.
- Keep natural language text separate from executable constraints.

## Done criteria
- File is valid JSONL.
- Every record has unique `id`.
- All points used in hypotheses are declared in `points`.
