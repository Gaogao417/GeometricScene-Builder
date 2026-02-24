---
name: reporting-standard
description: Use this skill when generating benchmark reports from run artifacts. It standardizes report fields, sorting, image embedding, and markdown/html outputs for comparability.
---

# Reporting Standard

Standardize benchmark report generation.

## Required outputs
- `report.md`
- `report.html`

## Required columns
- `problem_id`
- `recipe_name`
- `seed`
- `success`
- `solve_time_s`
- `fail_type`
- `image`
- `link`

## Ordering rules
1. `problem_id`
2. `recipe_name`
3. `seed`

## Rendering rules
- Fixed thumbnail size.
- Click-through full image links.
- Use relative paths under run directory.

See table template in `references/report-template.md`.

## Done criteria
- MD and HTML show identical row counts.
- Failed cases are visible (not dropped silently).
