# Agent: scorer-ui

## Role
Run manual scoring session and persist resumable ratings.

## Inputs
- run directory with `results.jsonl` and images
- scoring scale (default 1-5)

## Outputs
- `outputs/<run>/ratings.csv`
- optional `outputs/<run>/ratings_checkpoint.json`

## Workflow
1. Filter to successful cases with valid image path.
2. Show one image with metadata (`problem_id`, `recipe_name`, `seed`, `solve_time_s`).
3. Accept score 1-5 and optional comment.
4. Autosave every N records and support resume.

## Hard rules
- Do not overwrite existing ratings unless explicit merge mode is chosen.
- Keep one row per (`problem_id`,`recipe_name`,`seed`).
- Preserve reviewer timestamp.

## Completion criteria
- CSV schema valid and no duplicate keys.
- Progress can resume after interruption.
