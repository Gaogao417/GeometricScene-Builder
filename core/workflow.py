#!/usr/bin/env python3
"""
Agentic GeometricScene workflow.

The workflow accepts one teaching-oriented geometry request, asks an
OpenAI-compatible text model to write/revise a Wolfram GeometricScene,
renders it through Wolfram, asks an OpenAI-compatible vision model whether
the picture is usable, and retries with visual feedback up to max_retries.
"""

from __future__ import annotations

import argparse
import base64
import json
import multiprocessing as mp
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime import resolve_wolfram_kernel

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised in environments without deps.
    OpenAI = None  # type: ignore[assignment]

try:
    from wolframclient.evaluation import WolframLanguageSession
    from wolframclient.language import Global, wlexpr
except ImportError as exc:  # pragma: no cover
    WolframLanguageSession = None  # type: ignore[assignment]
    Global = None  # type: ignore[assignment]
    wlexpr = None  # type: ignore[assignment]
    WOLFRAM_IMPORT_ERROR = exc
else:
    WOLFRAM_IMPORT_ERROR = None


FORBIDDEN_WL_TOKENS = [
    "RunProcess",
    "StartProcess",
    "CreateFile",
    "DeleteFile",
    "DeleteDirectory",
    "RenameFile",
    "CopyFile",
    "Import[",
    "URLRead",
    "URLExecute",
    "Get[",
    "Put[",
    "<<",
]

SKILL_SETS = {
    "generate": [
        "wolfram-geometricscene-reference",
        "wolfram-schema-first-param-types",
        "dimensionless-constraints-library",
        "wolfram-python-integration-patterns",
        "windows-encoding-compatibility",
    ],
    "evaluate": [
        "human-rating-loop",
        "tool-output-standards",
    ],
    "finalize": [
        "agent-io-schema",
        "tool-output-standards",
    ],
}

DEFAULT_TEXT_MODELS = [
    "qwen3.5-plus",
    "qwen3.6-plus",
    "qwen3.6-flash",
    "qwen3.6-flash-2026-04-16",
    "qwen3.5-flash",
    "qwen3.5-flash-2026-02-23",
    "qwen3.5-35b-a3b",
    "qwen3.6-35b-a3b",
    "qwen3.5-122b-a10b",
    "qwen3.5-397b-a17b",
    "qwen3.6-27b",
    "qwen3.6-plus-2026-04-02",
    "qwen3.5-plus-2026-04-20",
    "qwen3.5-plus-2026-02-15",
    "deepseek-v4-flash",
]

DEFAULT_VISION_MODELS = [
    "qwen3.5-flash",
    "qwen3.6-flash",
    "qwen3.6-flash-2026-04-16",
    "qwen3.5-flash-2026-02-23",
    "qwen3.5-plus",
    "qwen3.6-plus",
    "qwen3.6-plus-2026-04-02",
    "qwen3.5-plus-2026-04-20",
    "qwen3.5-plus-2026-02-15",
    "qwen3.5-122b-a10b",
    "qwen3.5-35b-a3b",
    "qwen3.6-35b-a3b",
    "qwen3.5-397b-a17b",
    "qwen3.6-27b",
    "qwen3.6-max-preview",
]


class WorkflowState(TypedDict, total=False):
    request: Dict[str, Any]
    out_dir: str
    round_index: int
    max_retries: int
    scene_payload: Dict[str, Any]
    render_result: Dict[str, Any]
    vision_result: Dict[str, Any]
    history: List[Dict[str, Any]]
    skills_context: Dict[str, str]
    status: str
    error: str


class ModelPoolError(RuntimeError):
    def __init__(self, role: str, attempts: List[Dict[str, Any]]):
        super().__init__(
            f"All {role} models failed: "
            + json.dumps(attempts, ensure_ascii=False, default=_json_default)
        )
        self.role = role
        self.attempts = attempts


def _json_default(value: Any) -> str:
    return str(value)


def _read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("workflow request must be a JSON object")
    return data


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _skills_root() -> Path:
    return _project_root() / ".opencode" / "skills"


def _read_skill(skill_name: str, max_chars: int = 9000) -> str:
    skill_path = _skills_root() / skill_name / "SKILL.md"
    if not skill_path.exists():
        return f"[missing skill: {skill_name}]"
    text = skill_path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[skill truncated for prompt budget]"


def load_skills_context() -> Dict[str, str]:
    contexts: Dict[str, str] = {}
    for group, names in SKILL_SETS.items():
        parts = []
        for name in names:
            parts.append(f"## Skill: {name}\n\n{_read_skill(name)}")
        contexts[group] = "\n\n---\n\n".join(parts)
    return contexts


def _default_out_dir(prefix: str = "workflow") -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("outputs") / f"{prefix}_{timestamp}"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_local_env() -> None:
    root = _project_root()
    _load_env_file(root / ".env")
    _load_env_file(root / ".env.local")


def _env_first(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _split_models(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _dedupe_models(models: List[str]) -> List[str]:
    seen = set()
    deduped = []
    for model in models:
        if model not in seen:
            seen.add(model)
            deduped.append(model)
    return deduped


def _model_pool(
    config: Dict[str, Any],
    pool_key: str,
    single_keys: List[str],
    env_names: List[str],
    defaults: List[str],
) -> List[str]:
    candidates: List[str] = []
    for key in single_keys:
        candidates.extend(_split_models(config.get(key)))
    candidates.extend(_split_models(config.get(pool_key)))
    candidates.extend(_split_models(_env_first(*env_names)))
    candidates.extend(defaults)
    return _dedupe_models(candidates)


def _model_error_record(role: str, model: str, exc: Exception) -> Dict[str, str]:
    return {
        "role": role,
        "model": model,
        "error_type": exc.__class__.__name__,
        "error": str(exc),
    }


def _is_retryable_model_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "missing openai-compatible api key" in message:
        return False
    if "api key" in message and ("missing" in message or "not set" in message):
        return False
    return True


def _resolved_model_config(model_config: Dict[str, Any]) -> Dict[str, Any]:
    load_local_env()
    resolved = dict(model_config)
    resolved.setdefault(
        "base_url",
        _env_first("GSB_BASE_URL", "DASHSCOPE_BASE_URL", "OPENAI_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    text_models = _model_pool(
        resolved,
        "text_models",
        ["text_model", "model"],
        ["GSB_TEXT_MODELS", "DASHSCOPE_TEXT_MODELS", "GSB_TEXT_MODEL", "DASHSCOPE_TEXT_MODEL"],
        DEFAULT_TEXT_MODELS,
    )
    vision_models = _model_pool(
        resolved,
        "vision_models",
        ["vision_model"],
        ["GSB_VISION_MODELS", "DASHSCOPE_VISION_MODELS", "GSB_VISION_MODEL", "DASHSCOPE_VISION_MODEL", "VISION_MODEL"],
        DEFAULT_VISION_MODELS,
    )
    resolved["text_models"] = text_models
    resolved["vision_models"] = vision_models
    resolved.setdefault("text_model", text_models[0] if text_models else "")
    resolved.setdefault("vision_model", vision_models[0] if vision_models else "")
    resolved.setdefault(
        "api_key_env",
        _env_first("GSB_API_KEY_ENV") or "DASHSCOPE_API_KEY",
    )
    if "vision_base_url" not in resolved:
        vision_base_url = _env_first(
            "GSB_VISION_BASE_URL", "DASHSCOPE_VISION_BASE_URL", "VISION_BASE_URL"
        )
        if vision_base_url:
            resolved["vision_base_url"] = vision_base_url
    if "vision_api_key_env" not in resolved:
        vision_key_env = _env_first("GSB_VISION_API_KEY_ENV", "VISION_API_KEY_ENV")
        if vision_key_env:
            resolved["vision_api_key_env"] = vision_key_env
    return resolved


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("model response JSON must be an object")
    return parsed


def _make_client(model_config: Dict[str, Any], role: str = "text"):
    if OpenAI is None:
        raise RuntimeError("Missing dependency: install openai>=1.0.0")
    config = _resolved_model_config(model_config)
    if role == "vision":
        api_key = config.get("vision_api_key") or config.get("api_key") or os.getenv(
            config.get("vision_api_key_env")
            or config.get("api_key_env", "DASHSCOPE_API_KEY")
        )
        base_url = config.get("vision_base_url") or config.get("base_url")
    else:
        api_key = config.get("api_key") or os.getenv(
            config.get("api_key_env", "DASHSCOPE_API_KEY")
        )
        base_url = config.get("base_url")
    if not api_key:
        raise RuntimeError(f"Missing OpenAI-compatible API key for {role} model")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _text_model_json(
    request: Dict[str, Any],
    history: List[Dict[str, Any]],
    round_index: int,
    skills_context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    model_config = _resolved_model_config(request.get("model_config", {}))
    client = _make_client(model_config, "text")
    models = model_config.get("text_models", [])
    if not models:
        raise RuntimeError("No text models configured")

    system_prompt = (
        "You generate Wolfram Language GeometricScene code for math teaching diagrams. "
        "Return only valid JSON. Do not use Import, Get, file operations, URL access, "
        "or process execution. Prefer readable, non-degenerate diagrams. The PNG is "
        "only for evaluation; the final teaching renderer will consume the scene and "
        "diagram_spec.\n\n"
        "Use the following local skills as binding implementation guidance:\n\n"
        f"{(skills_context or {}).get('generate', '')}"
    )
    feedback = history[-1].get("vision_result") if history else None
    user_payload = {
        "problem_text": request.get("problem_text", ""),
        "grade_or_topic": request.get("grade_or_topic", ""),
        "teaching_focus": request.get("teaching_focus", []),
        "objects_hint": request.get("objects_hint", {}),
        "diagram_intent": request.get("diagram_intent", "synthetic_geometry"),
        "round_index": round_index,
        "previous_feedback": feedback,
        "required_json_schema": {
            "scene_code": "A complete Wolfram GeometricScene[...] expression.",
            "points": ["Point labels used in the scene, e.g. A, B, C"],
            "diagram_spec": {
                "type": "synthetic_geometry | coordinate_geometry",
                "objects": [],
                "teaching_focus": [],
            },
            "rationale": "Short reason for the chosen constraints.",
        },
    }

    attempts = []
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=float(model_config.get("temperature", 0.2)),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False),
                    },
                ],
            )
            content = response.choices[0].message.content or "{}"
            payload = _extract_json_object(content)
            if "scene_code" not in payload:
                raise ValueError("text model response missing scene_code")
            payload["model_used"] = model
            payload["model_attempts"] = attempts + [
                {"role": "text", "model": model, "status": "ok"}
            ]
            return payload
        except Exception as exc:
            attempts.append(_model_error_record("text", model, exc))
            if not _is_retryable_model_error(exc):
                break

    raise ModelPoolError("text", attempts)


def _validate_scene_code(scene_code: str) -> None:
    if "GeometricScene" not in scene_code:
        raise ValueError("scene_code must contain GeometricScene")
    for token in FORBIDDEN_WL_TOKENS:
        if token in scene_code:
            raise ValueError(f"scene_code contains forbidden token: {token}")


def _render_worker(
    queue: mp.Queue,
    wl_kernel: str,
    wl_dir: str,
    scene_code: str,
    seed: int,
    timeout_s: int,
    image_abs: str,
) -> None:
    try:
        if WOLFRAM_IMPORT_ERROR is not None:
            raise RuntimeError(f"Missing wolframclient: {WOLFRAM_IMPORT_ERROR}")
        with WolframLanguageSession(wl_kernel) as session:  # type: ignore[misc]
            wl_root = Path(wl_dir).as_posix()
            session.evaluate(wlexpr(f'Get["{wl_root}/scene_builders.wl"]'))  # type: ignore[misc]
            session.evaluate(wlexpr(f'Get["{wl_root}/bench_core.wl"]'))  # type: ignore[misc]
            session.evaluate(wlexpr("1+1"))  # type: ignore[misc]
            scene = session.evaluate(wlexpr(scene_code))  # type: ignore[misc]
            result = session.evaluate(  # type: ignore[operator]
                Global.SolveAndMeasure(
                    scene,
                    int(seed),
                    int(timeout_s),
                    True,
                    Path(image_abs).as_posix(),
                )
            )
            raw = dict(result) if hasattr(result, "items") else {}
            queue.put(_wl_to_python(raw))
    except Exception as exc:
        queue.put(
            {
                "success": False,
                "fail_type": "runtime_error",
                "message": str(exc),
                "solve_time_s": 0,
            }
        )


def _wl_to_python(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {_wl_to_python(k): _wl_to_python(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wl_to_python(item) for item in value]
    if hasattr(value, "name"):
        return str(value)
    if hasattr(value, "head") and hasattr(value, "args"):
        return [_wl_to_python(item) for item in value.args]
    return value


def _render_scene(
    scene_code: str,
    out_dir: Path,
    round_index: int,
    request: Dict[str, Any],
) -> Dict[str, Any]:
    _validate_scene_code(scene_code)
    round_dir = out_dir / "rounds" / f"round_{round_index}"
    round_dir.mkdir(parents=True, exist_ok=True)
    scene_path = round_dir / "scene.wl"
    scene_path.write_text(scene_code, encoding="utf-8")

    image_rel = f"rounds/round_{round_index}/scene.png"
    image_abs = out_dir / image_rel
    queue: mp.Queue = mp.Queue(maxsize=1)
    timeout_s = int(request.get("wolfram_timeout_s", request.get("timeout_s", 60)))
    hard_timeout_s = int(request.get("wolfram_hard_timeout_s", timeout_s + 20))
    wl_kernel = resolve_wolfram_kernel(request.get("wl_kernel"))
    wl_dir = Path(__file__).resolve().parent.parent / "wl"

    proc = mp.Process(
        target=_render_worker,
        args=(
            queue,
            wl_kernel,
            wl_dir.as_posix(),
            scene_code,
            int(request.get("seed", round_index + 1)),
            timeout_s,
            str(image_abs),
        ),
    )
    proc.start()
    proc.join(timeout=hard_timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
        return {
            "success": False,
            "fail_type": "host_watchdog_timeout",
            "message": f"Wolfram render exceeded {hard_timeout_s}s",
            "image_path": image_rel,
        }

    if queue.empty():
        return {
            "success": False,
            "fail_type": "worker_no_result",
            "message": "Wolfram worker returned no result",
            "image_path": image_rel,
        }

    result = queue.get()
    if result.get("success") and image_abs.exists():
        result["image_path"] = image_rel
    return result


def _image_data_url(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _evaluate_image(
    request: Dict[str, Any],
    render_result: Dict[str, Any],
    out_dir: Path,
    skills_context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if not render_result.get("success"):
        return {
            "usable": False,
            "score": 1,
            "defects": [render_result.get("fail_type", "render_failed")],
            "suggested_constraint_feedback": render_result.get(
                "message", "Render failed; generate a simpler valid GeometricScene."
            ),
        }

    image_rel = render_result.get("image_path")
    image_path = out_dir / image_rel if image_rel else None
    if not image_path or not image_path.exists():
        return {
            "usable": False,
            "score": 1,
            "defects": ["missing_image"],
            "suggested_constraint_feedback": "The render did not produce a PNG.",
        }

    model_config = _resolved_model_config(request.get("model_config", {}))
    client = _make_client(model_config, "vision")
    vision_models = model_config.get("vision_models", [])
    if not vision_models:
        raise RuntimeError("No vision models configured")

    prompt = {
        "task": "Evaluate whether this geometry diagram is usable for a student-facing math explanation.",
        "problem_text": request.get("problem_text", ""),
        "teaching_focus": request.get("teaching_focus", []),
        "local_skill_guidance": (skills_context or {}).get("evaluate", ""),
        "criteria": [
            "matches the problem objects and constraints",
            "not degenerate",
            "important points/segments/regions are visible",
            "labels would be placeable/readable",
            "coordinate axes are readable when needed",
            "does not visually imply false special properties",
        ],
        "required_json_schema": {
            "usable": "boolean",
            "score": "integer 1-5",
            "defects": ["short defect strings"],
            "suggested_constraint_feedback": "short actionable feedback for the next GeometricScene attempt",
        },
    }

    attempts = []
    for vision_model in vision_models:
        try:
            response = client.chat.completions.create(
                model=vision_model,
                temperature=float(model_config.get("vision_temperature", 0.0)),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(prompt, ensure_ascii=False),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": _image_data_url(image_path)},
                            },
                        ],
                    }
                ],
            )
            content = response.choices[0].message.content or "{}"
            payload = _extract_json_object(content)
            return {
                "usable": bool(payload.get("usable")),
                "score": int(payload.get("score", 1)),
                "defects": payload.get("defects", []),
                "suggested_constraint_feedback": payload.get(
                    "suggested_constraint_feedback", ""
                ),
                "model_used": vision_model,
                "model_attempts": attempts
                + [{"role": "vision", "model": vision_model, "status": "ok"}],
            }
        except Exception as exc:
            attempts.append(_model_error_record("vision", vision_model, exc))
            if not _is_retryable_model_error(exc):
                break

    raise ModelPoolError("vision", attempts)


def generate_scene_node(state: WorkflowState) -> WorkflowState:
    request = state["request"]
    round_index = state.get("round_index", 0)
    history = state.get("history", [])
    out_dir = Path(state["out_dir"])
    round_dir = out_dir / "rounds" / f"round_{round_index}"
    round_dir.mkdir(parents=True, exist_ok=True)

    try:
        scene_payload = _text_model_json(
            request,
            history,
            round_index,
            state.get("skills_context") or load_skills_context(),
        )
        _write_json(round_dir / "scene_payload.json", scene_payload)
        state["scene_payload"] = scene_payload
    except ModelPoolError as exc:
        scene_payload = {"model_attempts": exc.attempts}
        _write_json(round_dir / "scene_payload.json", scene_payload)
        state["scene_payload"] = scene_payload
        state["status"] = "failed"
        state["error"] = f"generate_scene_failed: {exc}"
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = f"generate_scene_failed: {exc}"
    return state


def render_wolfram_node(state: WorkflowState) -> WorkflowState:
    if state.get("status") == "failed":
        return state
    out_dir = Path(state["out_dir"])
    round_index = state.get("round_index", 0)
    round_dir = out_dir / "rounds" / f"round_{round_index}"
    try:
        scene_code = state["scene_payload"]["scene_code"]
        render_result = _render_scene(scene_code, out_dir, round_index, state["request"])
        _write_json(round_dir / "render_result.json", render_result)
        state["render_result"] = render_result
    except Exception as exc:
        render_result = {
            "success": False,
            "fail_type": "render_exception",
            "message": str(exc),
        }
        _write_json(round_dir / "render_result.json", render_result)
        state["render_result"] = render_result
    return state


def evaluate_image_node(state: WorkflowState) -> WorkflowState:
    if state.get("status") == "failed":
        return state
    out_dir = Path(state["out_dir"])
    round_index = state.get("round_index", 0)
    round_dir = out_dir / "rounds" / f"round_{round_index}"
    try:
        vision_result = _evaluate_image(
            state["request"],
            state["render_result"],
            out_dir,
            state.get("skills_context") or load_skills_context(),
        )
    except ModelPoolError as exc:
        vision_result = {
            "usable": False,
            "score": 1,
            "defects": ["vision_model_pool_failed"],
            "suggested_constraint_feedback": str(exc),
            "model_attempts": exc.attempts,
        }
    except Exception as exc:
        vision_result = {
            "usable": False,
            "score": 1,
            "defects": ["vision_evaluation_failed"],
            "suggested_constraint_feedback": str(exc),
        }
    _write_json(round_dir / "vision_result.json", vision_result)
    state["vision_result"] = vision_result
    return state


def update_history_node(state: WorkflowState) -> WorkflowState:
    history = state.get("history", [])
    history.append(
        {
            "round_index": state.get("round_index", 0),
            "scene_payload": state.get("scene_payload", {}),
            "render_result": state.get("render_result", {}),
            "vision_result": state.get("vision_result", {}),
        }
    )
    state["history"] = history
    if state.get("vision_result", {}).get("usable"):
        state["status"] = "ok"
    elif state.get("round_index", 0) >= state.get("max_retries", 3):
        state["status"] = "failed"
        state["error"] = "max_retries_exhausted"
    else:
        state["round_index"] = state.get("round_index", 0) + 1
    return state


def should_continue(state: WorkflowState) -> str:
    return "done" if state.get("status") in {"ok", "failed"} else "retry"


def _collect_model_attempts(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    attempts: List[Dict[str, Any]] = []
    for round_item in history:
        scene_payload = round_item.get("scene_payload", {})
        vision_result = round_item.get("vision_result", {})
        attempts.extend(scene_payload.get("model_attempts", []))
        attempts.extend(vision_result.get("model_attempts", []))
    return attempts


def finalize_node(state: WorkflowState) -> WorkflowState:
    out_dir = Path(state["out_dir"])
    history = state.get("history", [])
    final_round = history[-1] if history else {}
    scene_payload = final_round.get("scene_payload", {})
    render_result = final_round.get("render_result", {})

    if scene_payload.get("scene_code"):
        (out_dir / "final_geometric_scene.wl").write_text(
            scene_payload["scene_code"], encoding="utf-8"
        )
    final_spec = {
        "status": state.get("status", "failed"),
        "diagram_spec": scene_payload.get("diagram_spec", {}),
        "scene_code_path": "final_geometric_scene.wl",
        "image_path": render_result.get("image_path"),
        "round_count": len(history),
    }
    _write_json(out_dir / "final_diagram_spec.json", final_spec)

    result = {
        "status": state.get("status", "failed"),
        "error": state.get("error", ""),
        "out_dir": str(out_dir),
        "final_diagram_spec": "final_diagram_spec.json",
        "final_image_path": render_result.get("image_path"),
        "skills_used": SKILL_SETS,
        "model_attempts": _collect_model_attempts(history),
        "rounds": history,
    }
    _write_json(out_dir / "workflow_result.json", result)
    return state


def _run_without_langgraph(state: WorkflowState) -> WorkflowState:
    while True:
        state = generate_scene_node(state)
        state = render_wolfram_node(state)
        state = evaluate_image_node(state)
        state = update_history_node(state)
        if should_continue(state) == "done":
            return finalize_node(state)


def build_graph():
    # Phase 1 keeps orchestration in a simple Python loop. The step functions
    # above can be mapped to LangGraph nodes later without changing contracts.
    return None


def run_workflow(request: Dict[str, Any], out_dir: Path, request_path: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "rounds").mkdir(exist_ok=True)
    shutil.copy2(request_path, out_dir / "request.json")

    state: WorkflowState = {
        "request": request,
        "out_dir": str(out_dir),
        "round_index": 0,
        "max_retries": int(request.get("max_retries", 3)),
        "history": [],
        "skills_context": load_skills_context(),
    }
    app = build_graph()
    if app is None:
        final_state = _run_without_langgraph(state)
    else:
        final_state = app.invoke(state)

    result_path = out_dir / "workflow_result.json"
    if result_path.exists():
        return _read_json(result_path)
    return {
        "status": final_state.get("status", "failed"),
        "error": final_state.get("error", "workflow_result_missing"),
        "out_dir": str(out_dir),
    }


def generate_candidate_action(
    request: Dict[str, Any],
    out_dir: Path,
    round_index: int,
    history_path: Optional[Path] = None,
) -> Dict[str, Any]:
    history: List[Dict[str, Any]] = []
    if history_path and history_path.exists():
        loaded = _read_json(history_path)
        if isinstance(loaded.get("rounds"), list):
            history = loaded["rounds"]
        elif isinstance(loaded.get("history"), list):
            history = loaded["history"]
    round_dir = out_dir / "rounds" / f"round_{round_index}"
    round_dir.mkdir(parents=True, exist_ok=True)
    payload = _text_model_json(
        request,
        history,
        round_index,
        load_skills_context(),
    )
    _write_json(round_dir / "scene_payload.json", payload)
    return {
        "status": "ok",
        "action": "generate",
        "round_index": round_index,
        "scene_payload_path": str(round_dir / "scene_payload.json"),
        "skills_used": SKILL_SETS["generate"],
    }


def render_candidate_action(
    request: Dict[str, Any],
    scene_payload_path: Path,
    out_dir: Path,
    round_index: int,
) -> Dict[str, Any]:
    payload = _read_json(scene_payload_path)
    if "scene_code" not in payload:
        raise ValueError("scene_payload missing scene_code")
    render_result = _render_scene(payload["scene_code"], out_dir, round_index, request)
    round_dir = out_dir / "rounds" / f"round_{round_index}"
    _write_json(round_dir / "render_result.json", render_result)
    return {
        "status": "ok" if render_result.get("success") else "failed",
        "action": "render",
        "round_index": round_index,
        "render_result_path": str(round_dir / "render_result.json"),
        "render_result": render_result,
    }


def evaluate_image_action(
    request: Dict[str, Any],
    render_result_path: Path,
    out_dir: Path,
    round_index: int,
) -> Dict[str, Any]:
    render_result = _read_json(render_result_path)
    vision_result = _evaluate_image(
        request,
        render_result,
        out_dir,
        load_skills_context(),
    )
    round_dir = out_dir / "rounds" / f"round_{round_index}"
    _write_json(round_dir / "vision_result.json", vision_result)
    return {
        "status": "ok",
        "action": "evaluate",
        "round_index": round_index,
        "vision_result_path": str(round_dir / "vision_result.json"),
        "vision_result": vision_result,
        "skills_used": SKILL_SETS["evaluate"],
    }


def skill_context_action(out_dir: Path) -> Dict[str, Any]:
    context = load_skills_context()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "skills_context.json"
    _write_json(path, {"status": "ok", "skills_used": SKILL_SETS, "context": context})
    return {
        "status": "ok",
        "action": "skill_context",
        "skills_context_path": str(path),
        "skills_used": SKILL_SETS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run agentic GeometricScene workflow")
    parser.add_argument(
        "--action",
        choices=["run", "generate", "render", "evaluate", "skill_context"],
        default="run",
        help="workflow action; run executes the full retry loop",
    )
    parser.add_argument("--request", help="workflow request JSON path")
    parser.add_argument("--out", help="output directory")
    parser.add_argument("--round-index", type=int, default=0, help="round index for single-step actions")
    parser.add_argument("--history", help="workflow_result.json or history JSON for generate action")
    parser.add_argument("--scene-payload", help="scene_payload.json path for render action")
    parser.add_argument("--render-result", help="render_result.json path for evaluate action")
    args = parser.parse_args()

    if args.out:
        out_dir = Path(args.out)
    else:
        out_dir = _default_out_dir("workflow")

    try:
        if args.action == "skill_context":
            result = skill_context_action(out_dir)
        else:
            if not args.request:
                raise ValueError("--request is required for this action")
            request_path = Path(args.request)
            if not request_path.exists():
                raise FileNotFoundError(f"Request file not found: {request_path}")
            request = _read_json(request_path)

            if args.action == "run":
                result = run_workflow(request, out_dir, request_path)
            elif args.action == "generate":
                result = generate_candidate_action(
                    request,
                    out_dir,
                    args.round_index,
                    Path(args.history) if args.history else None,
                )
            elif args.action == "render":
                if not args.scene_payload:
                    raise ValueError("--scene-payload is required for render action")
                result = render_candidate_action(
                    request,
                    Path(args.scene_payload),
                    out_dir,
                    args.round_index,
                )
            elif args.action == "evaluate":
                if not args.render_result:
                    raise ValueError("--render-result is required for evaluate action")
                result = evaluate_image_action(
                    request,
                    Path(args.render_result),
                    out_dir,
                    args.round_index,
                )
            else:
                raise ValueError(f"Unknown action: {args.action}")
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, default=_json_default))


if __name__ == "__main__":
    main()
