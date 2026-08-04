# [x] Task 5: Migrate Error Sites in `main.py` and `metrics.py`

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

Convert remaining error sites and implement per-input metrics.

## Dependencies

- Task 1 (ReportError dataclass must exist)
- Tasks 2–4 (all error sites migrated, so the pipeline uses `list[ReportError]` consistently)

## Implementation

### `src/syntagmax/main.py`

- The single-root check produces `ReportError(category=CAT_STRUCTURE, input_record=None)`.
- Implement metrics computation:
  - Always compute aggregate metrics across all artifacts → `report.metrics`.
  - If >1 input records contribute to `requirement_type`, additionally compute per-input metrics by filtering artifacts by `artifact.record.name` → `report.metrics_by_input = [(record_name, metrics_benedict), ...]`.

### `src/syntagmax/metrics.py`

- "No requirements found" error → `ReportError(category=CAT_STRUCTURE, input_record=None, message="Metrics: No requirements found")`.
- Accept an optional `input_record_name` parameter to `calculate_metrics` for per-input calls.
- Accept optional pre-filtered artifact subset for per-input computation.

## Test Requirements

- With multiple input records, `report.metrics` is populated (aggregate) AND `report.metrics_by_input` has one entry per input.
- With single input record, `report.metrics` is populated and `report.metrics_by_input` is None.
- "No requirements found" is a `ReportError`.

## Demo

Run analysis on multi-input example; report contains per-input metrics sections.

## Files Modified

- `src/syntagmax/main.py`
- `src/syntagmax/metrics.py`
- `src/syntagmax/report.py` (add `metrics_by_input` field to `Report` dataclass)
