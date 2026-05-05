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
  - `python core/bench.py --config <config_path> --problems <problems_path> [--out <out_dir>]`
- Success output (JSON string):
  - `{"status":"ok","run_dir":"...","total_cases":123}`
- Failure output:
  - `{"status":"error","message":"..."}`

## Tool 2: build_report(run_dir)
- Purpose: build markdown and HTML reports from run artifacts.
- Input:
  - `run_dir` (string, required)
- Command:
  - `python core/report.py --run_dir <run_dir>`
  - `python core/analyze.py --run_dir <run_dir>`
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

## Tool 4: run_diagram_workflow(request_path, out_dir?)
- Purpose: run the full agentic single-problem diagram loop.
- Input:
  - `request_path` (string, required): DiagramRequest JSON.
  - `out_dir` (string, optional): workflow output directory.
- Command:
  - `python core/workflow.py --action run --request <request_path> [--out <out_dir>]`
- Success output:
  - `workflow_result.json` content, including `status`, `out_dir`, `rounds`, `skills_used`, `final_diagram_spec`, and `final_image_path`.

## Tool 5: get_diagram_skill_context(out_dir?)
- Purpose: write the local diagram workflow skill context to JSON for agent inspection/debugging.
- Input:
  - `out_dir` (string, optional): directory for `skills_context.json`.
- Command:
  - `python core/workflow.py --action skill_context [--out <out_dir>]`
- Success output:
  - `{"status":"ok","skills_context_path":"...","skills_used":{...}}`

## Tool 6: generate_diagram_candidate(request_path, out_dir?, round_index?, history_path?)
- Purpose: generate one candidate `scene_payload.json` without rendering it.
- Input:
  - `request_path` (string, required): DiagramRequest JSON.
  - `out_dir` (string, optional): workflow output directory.
  - `round_index` (number, optional): retry round index, default `0`.
  - `history_path` (string, optional): previous `workflow_result.json` or history JSON.
- Command:
  - `python core/workflow.py --action generate --request <request_path> --round-index <n> [--out <out_dir>] [--history <history_path>]`
- Success output:
  - `{"status":"ok","scene_payload_path":"...","skills_used":[...]}`

## Tool 7: render_diagram_candidate(request_path, scene_payload_path, out_dir?, round_index?)
- Purpose: render one generated candidate through Wolfram.
- Input:
  - `request_path` (string, required): DiagramRequest JSON.
  - `scene_payload_path` (string, required): `scene_payload.json`.
  - `out_dir` (string, optional): workflow output directory.
  - `round_index` (number, optional): retry round index, default `0`.
- Command:
  - `python core/workflow.py --action render --request <request_path> --scene-payload <scene_payload_path> --round-index <n> [--out <out_dir>]`
- Success output:
  - `{"status":"ok|failed","render_result_path":"...","render_result":{...}}`

## Tool 8: evaluate_diagram_image(request_path, render_result_path, out_dir?, round_index?)
- Purpose: evaluate one rendered diagram image with the configured vision model.
- Input:
  - `request_path` (string, required): DiagramRequest JSON.
  - `render_result_path` (string, required): `render_result.json`.
  - `out_dir` (string, optional): workflow output directory.
  - `round_index` (number, optional): retry round index, default `0`.
- Command:
  - `python core/workflow.py --action evaluate --request <request_path> --render-result <render_result_path> --round-index <n> [--out <out_dir>]`
- Success output:
  - `{"status":"ok","vision_result_path":"...","vision_result":{...},"skills_used":[...]}`

## Shared validation rules
- Reject relative paths that escape workspace root.
- Check required files exist before execution.
- Return machine-readable JSON only.
- Never delete outputs by default.
- Keep each workflow attempt under `rounds/round_<n>/`.
- Treat `max_retries=3` as at most three revisions after the initial candidate.

## Recommended implementation notes
- Keep each tool as a thin wrapper around one script.
- Keep heavy logic in `core/` for easier testing.
- Use stable run directories (`outputs/run_YYYYMMDD_HHMMSS`).
