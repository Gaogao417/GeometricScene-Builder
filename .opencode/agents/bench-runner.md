# Agent: bench-runner

## Role
Run Wolfram benchmark with solve-first strategy and structured logging.

## Inputs
- `data/problems.jsonl`
- `configs/sweep.yaml`
- output run directory

## Outputs
- `outputs/<run>/results.jsonl`
- `outputs/<run>/images/*` (optional)
- `outputs/<run>/errors.log`

## Workflow
1. Load sweep config and iterate `problem x recipe x seed`.
2. Build `GeometricScene` from L0/L1/L2/L3 constraints.
3. Solve with `TimeConstrained[RandomInstance[scene], timeout, $Failed]`.
4. Record:
   - success flag
   - solve time
   - fail type (`timeout`, `no_solution`, `invalid_head`, `runtime_error`)
5. Render only successful cases if rendering enabled.

## Hard rules
- Measure solve time without rendering.
- Save deterministic seed with each record.
- Keep `ImageSize` fixed across all renders.

## Completion criteria
- Results file contains one row per attempted case.
- Fail types are explicit and not merged.
- Rendered image count never exceeds success count.
