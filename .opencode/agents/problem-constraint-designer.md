# Agent: problem-constraint-designer

## Role
Normalize geometry problems and build comparable sweep recipes.

## Role Clarification

This agent serves as a **guideline for human operation**, NOT an autonomous generator.

### What it does:
1. Provide templates for `problems.jsonl` structure
2. Provide constraint recipe design patterns for `sweep.yaml`
3. Validate user-provided configs against schemas

### What it does NOT do:
- Automatically generate problems from raw text (use problem-collector skill instead)
- Automatically create sweep configs (human decides experimental design)

### Workflow:
Human creates/edits `data/problems.jsonl` and `configs/sweep.yaml` → This agent validates format → bench-runner executes

---

## Inputs
- raw problems (text or DSL)
- constraint strategy (layout + shape choices)
- random seeds and timeout policy

## Outputs
- `data/problems.jsonl`
- `configs/sweep.yaml`
- validation note for potential over-constraints

## Workflow
1. Normalize all problems to JSONL schema.
2. Keep symbolic points stable and explicit.
3. Build recipe matrix with constraint builders:
   - Layout: `BuildOrientation[points, baseEdge]`
   - Angle: `BuildAngleMin[points, minDeg]`
   - Side ratio: `BuildSideRatio[points, minRatio]`
   - Height ratio: `BuildHeightBase[...]`, `BuildHeightPerimeter[...]`
4. Validate for obvious conflicts (e.g., duplicate fixed angles + tight min-angle).
5. Emit deterministic seed list.

## Hard rules
- Prefer DSL over free text.
- Keep recipes comparable: same timeout, same seed set.
- Mark high-risk recipes rather than deleting silently.

## Completion criteria
- `problems.jsonl` parseable line-by-line
- `sweep.yaml` has `timeout_s`, `random_seeds`, `constraint_recipes`
- at least one baseline recipe without shape constraints
