# Geo Custom Tools Spec

This document defines custom tools under `.opencode/tools`.
Implementation entry: `geo-tools.ts` (`GeoToolsPlugin`).

## Tool 1: run_sweep(config_path, out_dir?, problems_path?)
- Purpose: run benchmark from a sweep config.
- Input:
  - `config_path` (string, required)
  - `out_dir` (string, optional)
  - `problems_path` (string, optional, default `data/problems.jsonl`)
- Command:
  - `python scripts/bench.py --config <config_path> --problems <problems_path> [--out <out_dir>]`
- Success output (JSON string):
  - `{"status":"ok","run_dir":"...","total_cases":123}`
- Failure output:
  - `{"status":"error","message":"..."}`

## Tool 2: build_report(run_dir)
- Purpose: build markdown and HTML reports from run artifacts.
- Input:
  - `run_dir` (string, required)
- Command:
  - `python scripts/report.py --run_dir <run_dir>`
  - `python scripts/analyze.py --run_dir <run_dir>`
- Success output:
  - `{"status":"ok","report":"...","analysis":"..."}`

## Tool 3: launch_rater(run_dir)
- Purpose: launch manual scoring UI.
- Input:
  - `run_dir` (string, required)
- Command:
  - `streamlit run app/rate_streamlit.py -- --run_dir <run_dir>`
- Success output:
  - `{"status":"ok","ui":"started"}`

## Shared validation rules
- Reject relative paths that escape workspace root.
- Check required files exist before execution.
- Return machine-readable JSON only.
- Never delete outputs by default.

## Recommended implementation notes
- Keep each tool as a thin wrapper around one script.
- Keep heavy logic in `scripts/` for easier testing.
- Use stable run directories (`outputs/run_YYYYMMDD_HHMMSS`).
