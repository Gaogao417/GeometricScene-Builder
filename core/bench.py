#!/usr/bin/env python3
"""
Geometric Scene Benchmark Runner

**定位**: bench-runner agent 的执行工具
**调用方**: geo-orchestrator (通过 geo-tools.ts)
**输入**:
  - data/problems.jsonl (由 problem-collector agent 生成)
  - configs/sweep.yaml (由 problem-constraint-designer agent 生成)
**输出**:
  - outputs/run_*/results.jsonl (供 analyst-reporter agent 使用)
  - outputs/run_*/images/ (供 scorer-ui agent 使用)

Usage: python bench.py --config <sweep.yaml> --problems <problems.jsonl> --out <output_dir>
"""

import json
import time
import os
import sys
import shutil
import threading
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from wolframclient.language.expression import WLSymbol
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime import resolve_wolfram_kernel

# Import constraint builders (core library)
from core import BuildOrientation, AssembleConstraints, AssembleQualitativeConstraints

try:
    from wolframclient.evaluation import WolframLanguageSession
    from wolframclient.language import wl, wlexpr, Global
except ImportError as e:
    print(json.dumps({"status": "error", "message": f"Missing wolframclient: {e}"}))
    sys.exit(1)


def wl_to_python(val: Any) -> Any:
    """Recursively convert wolframclient return values (WLSymbol, WLFunction, etc.) to native Python for JSON serialization."""
    if val is None:
        return None
    if isinstance(val, dict):
        return {wl_to_python(k): wl_to_python(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [wl_to_python(x) for x in val]
    # WLSymbol and other WL types: convert to string
    if hasattr(val, "name"):
        return str(val)
    if hasattr(val, "head") and hasattr(val, "args"):
        return [wl_to_python(x) for x in val.args]
    return val


def load_problems(problems_path: str) -> List[Dict]:
    """Load problems from JSONL file or JSON array/object."""
    with open(problems_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # Try JSONL format first (each line is a JSON object)
    # JSONL files have multiple lines, each starting with '{'
    lines = content.split("\n")
    if len(lines) > 1 and all(
        line.strip().startswith("{") for line in lines if line.strip()
    ):
        problems = []
        for line in lines:
            if line.strip():
                problems.append(json.loads(line))
        return problems

    # Parse as JSON array or single object
    data = json.loads(content)
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return [data]
    else:
        raise ValueError(f"Expected JSON array or object, got {type(data).__name__}")


def load_config(config_path: str) -> Dict:
    """Load sweep configuration from YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_single_case(
    session: WolframLanguageSession,
    problem: Dict,
    recipe: Dict,
    seed: int,
    timeout: int,
    render: bool,
    out_dir: Path,
) -> Dict:
    """Run a single benchmark case. Pass Python/wl types directly to evaluate()."""
    try:
        problem_id = problem["id"]
        recipe_name = recipe["name"]
        points_raw = problem.get("points", [])
        base_edge_raw = problem.get("base_edge", [])
        base_hypotheses = problem.get("base_hypotheses_wl", [])

        # WL expressions - passed directly, wolframclient auto-serializes
        # 不准用wl.Symbol, 而是用WLSymbol
        points_wl = wl.List(*[WLSymbol(p) for p in points_raw])
        base_edge_wl = wl.List(*[WLSymbol(p) for p in base_edge_raw])
        base_hyp_wl = wl.List(*[wlexpr(h) for h in base_hypotheses])

        # Pipeline: 组装约束 (扁平化，无层级概念)
        all_constraints = []

        # 1. 布局约束 (可选)
        layout = recipe.get("layout") or {}
        if layout.get("triangle_base_horizontal"):
            all_constraints.append(BuildOrientation(points_wl, base_edge_wl))

        # 1.5. 定性约束 (可选)
        # 定性约束需要从 problem 的 qualitative_objects 字段获取几何对象
        # 约束对象必须来自题干给定的几何对象（不能是推理出的）
        qualitative_configs = recipe.get("qualitative")
        if qualitative_configs:
            qualitative_objects = problem.get("qualitative_objects", {})
            qualitative_constraints = AssembleQualitativeConstraints(
                qualitative_configs, qualitative_objects, points_raw
            )
            all_constraints.extend(qualitative_constraints)

        # 2. 形状约束 (正交组合，无层级关系)
        shape_configs = recipe.get("shape", [])
        all_constraints.extend(
            AssembleConstraints(points_wl, base_edge_wl, shape_configs)
        )

        layers_wl = wl.List(*all_constraints)

        # Unique image path per case: out_dir/images/{problem_id}_{recipe_name}_{seed}.png
        image_path_rel = f"images/{problem_id}_{recipe_name}_{seed}.png"
        image_path_abs = (
            (out_dir / image_path_rel).resolve().as_posix() if render else ""
        )

        # Build GeometricScene code for reproducibility (for debugging/failure analysis)
        # This allows copy-pasting into Mathematica to reproduce the exact scene
        base_hyps_str = ",\n    ".join(base_hypotheses)
        layers_str = ",\n    ".join([str(constraint) for constraint in all_constraints])
        scene_code_for_log = (
            "GeometricScene[\n"
            f"  {{{', '.join(points_raw)}}},\n"
            "  {\n"
            f"    {base_hyps_str},\n"
            f"    {layers_str}\n"
            "  }\n"
            "]"
        )

        result = session.evaluate(
            Global.SolveSingleCase(
                problem_id,
                recipe_name,
                points_wl,
                base_hyp_wl,
                layers_wl,
                seed,
                timeout,
                render,
                image_path_abs,
            )
        )

        # Convert WL Association to native Python dict (handles WLSymbol, nested WL types)
        raw_dict = dict(result) if hasattr(result, "items") else {}
        result_dict = wl_to_python(raw_dict)

        # Add recipe label
        result_dict["recipe_label"] = recipe.get("name", "unknown")

        # Store relative image_path for report/streamlit (they use run_dir / image_path)
        if result_dict.get("image_path") and render:
            result_dict["image_path"] = image_path_rel

        # Add GeometricScene code for debugging (especially on failure)
        result_dict["geometric_scene_code"] = scene_code_for_log

        return result_dict

    except Exception as e:
        return {
            "problem_id": problem["id"],
            "recipe_name": recipe["name"],
            "seed": seed,
            "success": False,
            "fail_type": "runtime_error",
            "solve_time_s": 0,
            "message": str(e),
        }


def _run_single_case_worker(
    result_queue: mp.Queue,
    wl_kernel: str,
    wl_dir: str,
    problem: Dict,
    recipe: Dict,
    seed: int,
    timeout: int,
    render: bool,
    out_dir: str,
    startup_retries: int,
    retry_backoff_s: float,
) -> None:
    """Run one case in isolated process so host can enforce hard timeout."""
    last_error = ""
    for attempt in range(1, startup_retries + 1):
        try:
            with WolframLanguageSession(wl_kernel) as session:
                session.evaluate(wlexpr(f'Get["{wl_dir}/scene_builders.wl"]'))
                session.evaluate(wlexpr(f'Get["{wl_dir}/bench_core.wl"]'))
                # Session warm-up to reduce first-eval jitter.
                session.evaluate(wlexpr("1+1"))
                result = run_single_case(
                    session, problem, recipe, seed, timeout, render, Path(out_dir)
                )
            break
        except Exception as e:
            last_error = str(e)
            if attempt >= startup_retries:
                result = {
                    "problem_id": problem["id"],
                    "recipe_name": recipe["name"],
                    "seed": seed,
                    "success": False,
                    "fail_type": "worker_error",
                    "solve_time_s": 0,
                    "message": f"session startup failed after {startup_retries} attempts: {last_error}",
                }
            else:
                time.sleep(retry_backoff_s * attempt)

    try:
        result_queue.put(result)
    except Exception:
        pass


def run_single_case_with_watchdog(
    wl_kernel: str,
    wl_dir: Path,
    problem: Dict,
    recipe: Dict,
    seed: int,
    timeout: int,
    render: bool,
    out_dir: Path,
    hard_timeout_s: int,
    startup_retries: int,
    retry_backoff_s: float,
) -> Dict:
    """Run one benchmark case with hard timeout enforced by host process."""
    result_queue: mp.Queue = mp.Queue(maxsize=1)
    proc = mp.Process(
        target=_run_single_case_worker,
        args=(
            result_queue,
            wl_kernel,
            wl_dir.as_posix(),
            problem,
            recipe,
            seed,
            timeout,
            render,
            str(out_dir),
            startup_retries,
            retry_backoff_s,
        ),
    )
    proc.start()
    proc.join(timeout=hard_timeout_s)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=2)

        return {
            "problem_id": problem["id"],
            "recipe_name": recipe["name"],
            "seed": seed,
            "success": False,
            "fail_type": "host_watchdog_timeout",
            "solve_time_s": float(timeout),
            "solver_wall_time_s": float(hard_timeout_s),
            "message": f"Host watchdog timeout after {hard_timeout_s}s",
        }

    if proc.exitcode != 0:
        return {
            "problem_id": problem["id"],
            "recipe_name": recipe["name"],
            "seed": seed,
            "success": False,
            "fail_type": "worker_crash",
            "solve_time_s": 0,
            "message": f"Worker exited with code {proc.exitcode}",
        }

    if not result_queue.empty():
        return result_queue.get()

    return {
        "problem_id": problem["id"],
        "recipe_name": recipe["name"],
        "seed": seed,
        "success": False,
        "fail_type": "worker_no_result",
        "solve_time_s": 0,
        "message": "Worker exited without result payload",
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Geometric Scene Benchmark Runner")
    parser.add_argument("--config", required=True, help="Sweep configuration YAML path")
    parser.add_argument("--problems", required=True, help="Problems JSONL path")
    parser.add_argument(
        "--out",
        required=False,
        help="Output directory (default: outputs/run_TIMESTAMP)",
    )
    args = parser.parse_args()

    # Validate input files
    config_path = Path(args.config)
    problems_path = Path(args.problems)

    if not config_path.exists():
        print(
            json.dumps(
                {"status": "error", "message": f"Config file not found: {config_path}"}
            )
        )
        sys.exit(1)

    if not problems_path.exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": f"Problems file not found: {problems_path}",
                }
            )
        )
        sys.exit(1)

    # Load config and problems
    config = load_config(config_path)
    problems = load_problems(problems_path)

    # Create output directory
    if args.out:
        out_dir = Path(args.out)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path("outputs") / f"run_{timestamp}"

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "images").mkdir(exist_ok=True)

    inputs_dir = out_dir / "inputs"
    inputs_dir.mkdir(exist_ok=True)
    shutil.copy2(config_path, inputs_dir / "sweep.yaml")
    shutil.copy2(problems_path, inputs_dir / "problems.jsonl")
    print(f"Input files backed up to {inputs_dir}", flush=True)

    wl_dir = Path(__file__).resolve().parent.parent / "wl"
    if not wl_dir.exists():
        print(json.dumps({"status": "error", "message": f"WL dir not found: {wl_dir}"}))
        sys.exit(1)

    # JSON serializer helper
    def _json_default(obj):
        if hasattr(obj, "name"):
            return str(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    # Open results file in append mode for streaming writes
    results_path = out_dir / "results.jsonl"
    results_count = 0

    wl_kernel = resolve_wolfram_kernel(config.get("wl_kernel"))
    timeout = config.get("timeout_s", 60)
    render_images = config.get("render_images", True)
    seeds = config.get("random_seeds", [1])
    recipes = config.get("constraint_recipes", [])
    watchdog_grace_s = int(config.get("watchdog_grace_s", 20))
    hard_timeout_s = timeout + watchdog_grace_s

    total_cases = len(problems) * len(recipes) * len(seeds)
    all_cases = []
    for problem in problems:
        for recipe in recipes:
            for seed in seeds:
                all_cases.append((problem, recipe, seed))

    max_parallel_cases = int(config.get("max_parallel_cases", 1))
    startup_retries = int(config.get("startup_retries", 2))
    retry_backoff_s = float(config.get("retry_backoff_s", 2.0))
    max_parallel_cases = max(1, min(max_parallel_cases, total_cases))

    print(
        f"Running {len(problems)} problems × {len(recipes)} recipes × {len(seeds)} seeds = {total_cases} cases",
        flush=True,
    )
    print(f"Timeout: {timeout}s, HostWatchdog: {hard_timeout_s}s", flush=True)
    print(
        f"Parallel: {max_parallel_cases}, StartupRetries: {startup_retries}", flush=True
    )
    print(f"Render: {render_images}", flush=True)
    print(f"Output: {out_dir}", flush=True)
    print(f"Results will be streamed to: {results_path}", flush=True)
    print(flush=True)

    def run_case(idx: int, problem: Dict, recipe: Dict, seed: int):
        print(
            f"[{idx}/{total_cases}] {problem['id']} × {recipe['name']} (seed={seed})",
            flush=True,
        )
        case_start = time.time()
        stop_heartbeat = threading.Event()

        def heartbeat():
            while not stop_heartbeat.wait(5):
                elapsed = time.time() - case_start
                over = (
                    " [超过配置timeout，仍在等待Wolfram返回]"
                    if elapsed > timeout
                    else ""
                )
                hard_over = (
                    " [已超过host watchdog阈值，将终止子进程]"
                    if elapsed > hard_timeout_s
                    else ""
                )
                print(
                    f"  ... still running, wall={elapsed:.1f}s (timeout={timeout}s, hard={hard_timeout_s}s){over}{hard_over}",
                    flush=True,
                )

        hb_thread = threading.Thread(target=heartbeat, daemon=True)
        hb_thread.start()
        try:
            result = run_single_case_with_watchdog(
                wl_kernel=wl_kernel,
                wl_dir=wl_dir,
                problem=problem,
                recipe=recipe,
                seed=seed,
                timeout=timeout,
                render=render_images,
                out_dir=out_dir,
                hard_timeout_s=hard_timeout_s,
                startup_retries=startup_retries,
                retry_backoff_s=retry_backoff_s,
            )
        finally:
            stop_heartbeat.set()
            hb_thread.join(timeout=0.2)

        wall = time.time() - case_start
        return idx, wall, result

    with open(results_path, "a", encoding="utf-8") as results_file:
        if max_parallel_cases == 1:
            for idx, (problem, recipe, seed) in enumerate(all_cases, start=1):
                _, wall, result = run_case(idx, problem, recipe, seed)
                status = "OK" if result.get("success") else "FAIL"
                t = result.get("solve_time_s", "N/A")
                fail = result.get("fail_type", "")
                build_t = result.get("scene_build_time_s", "N/A")
                solver_wall_t = result.get("solver_wall_time_s", "N/A")
                print(
                    f"  {status} solve={t}s build={build_t}s solver_wall={solver_wall_t}s wall={wall:.1f}s {fail}",
                    flush=True,
                )
                results_file.write(
                    json.dumps(result, ensure_ascii=False, default=_json_default) + "\n"
                )
                results_file.flush()
                print(flush=True)
        else:
            with ThreadPoolExecutor(max_workers=max_parallel_cases) as executor:
                future_map = {
                    executor.submit(run_case, idx, problem, recipe, seed): idx
                    for idx, (problem, recipe, seed) in enumerate(all_cases, start=1)
                }
                for future in as_completed(future_map):
                    idx, wall, result = future.result()
                    results_count += 1
                    status = "OK" if result.get("success") else "FAIL"
                    t = result.get("solve_time_s", "N/A")
                    fail = result.get("fail_type", "")
                    build_t = result.get("scene_build_time_s", "N/A")
                    solver_wall_t = result.get("solver_wall_time_s", "N/A")
                    print(
                        f"  [{idx}/{total_cases}] {status} solve={t}s build={build_t}s solver_wall={solver_wall_t}s wall={wall:.1f}s {fail}",
                        flush=True,
                    )
                    results_file.write(
                        json.dumps(result, ensure_ascii=False, default=_json_default)
                        + "\n"
                    )
                    results_file.flush()
                    print(flush=True)

    print(f"Results saved to {results_path}", flush=True)

    # Return success
    print(
        json.dumps(
            {"status": "ok", "run_dir": str(out_dir), "total_cases": total_cases}
        )
    )


if __name__ == "__main__":
    main()
