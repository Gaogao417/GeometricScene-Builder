# Problem JSONL Schema

## Minimal schema

```json
{
  "id": "p0001",
  "text": "(optional) question text",
  "dsl": {},
  "points": ["A", "B", "C"],
  "base_hypotheses_wl": [
    "AB == AC",
    "BC == 6"
  ],
  "meta": {
    "source": "manual"
  }
}
```

## Recommended optional fields
- `base_edge`: `["B", "C"]`
- `known_angles`: `[{"vertex": "B", "value_deg": 40}]`
- `constructed_points`: `{"D": "Midpoint[{B,C}]"}`
- `difficulty`: `easy|medium|hard`

## Validation checklist
- `id` unique
- `points` non-empty
- `base_hypotheses_wl` is array of strings
- symbols used in hypotheses belong to `points` or construction outputs
