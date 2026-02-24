---
name: analysis-standard
description: Use this skill when analyzing benchmark results plus human ratings to produce score/time tradeoff conclusions, Pareto candidates, and next-iteration constraint recommendations.
---

# Analysis Standard

Produce decision-ready analysis from `results.jsonl` and `ratings.csv`.

## Required aggregates per recipe
- success rate
- timeout rate
- solve time p50 and p90
- mean rating and rating count

## Required plots
- rating vs solve time scatter
- rating vs constraint strength trend
- recipe-level Pareto chart

## Decision rule
Prefer recipes on Pareto frontier. If two candidates are close, choose higher success rate and lower p90.

## Statistical hygiene
- show sample size for every number
- separate unrated from low-rated
- report confidence caveat for small samples

See `references/analysis-playbook.md`.

## Done criteria
- output `analysis_report.html`
- output concise recommendation with 1-3 candidate recipes
