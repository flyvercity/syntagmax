# [x] Task 6: Report Grouping Helper and Updated Template

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

Add `errors_grouped()` method to `Report` and rewrite `report.j2` with the new grouped structure.

## Dependencies

- Task 1 (ReportError, CANONICAL_CATEGORY_ORDER, GLOBAL_INPUT must exist)
- Task 5 (Report dataclass has `metrics_by_input` and `report_config` fields)

## Implementation

### `src/syntagmax/report.py`

- Add `errors_grouped() -> dict[str, list[tuple[str, list[ReportError]]]]` method:
  - Normalises all errors via `ReportError.from_any()` before grouping (defensive against stray strings).
  - Groups errors by `input_record` (using "Global" for `None`).
  - Within each input, groups by `category` sorted by `CANONICAL_CATEGORY_ORDER`.
  - Returns `OrderedDict` with "Global" first (if any), then input records in config order.
- Add `report_config` field to `Report` dataclass (set in `main.py` from `config.report`).

### `src/syntagmax/resources/report.j2`

- Errors section: iterate `report.errors_grouped()`, render `### {input_name} ({count} errors)` then `#### {category_name} ({count})` with numbered items.
- Metrics section: always render aggregate metrics first. If `report.metrics_by_input`, render additional per-input subsections underneath.
- Impact section: unchanged (flat).
- Category names use `{{ _(...) }}` for localisation.

## Test Requirements

- `Report` with errors from multiple inputs groups correctly.
- `Report` with only global errors renders "Global" section.
- Empty errors still produces no "Errors" section.
- Categories are sorted by `CANONICAL_CATEGORY_ORDER` (extraction before schema before attribute, etc.).
- Plain string errors in the list do not crash rendering (coerced via `from_any()`).
- Aggregate metrics always rendered; per-input metrics render when present.
- Flat metrics (single input) renders aggregate only without "by input" subsection.

## Demo

`syntagmax --render-tree --cwd ./example/obsidian-driver analyze` produces a grouped report with input sections.

## Files Modified

- `src/syntagmax/report.py`
- `src/syntagmax/resources/report.j2`
- `tests/test_report.py` (adapt existing tests to use `ReportError` objects)
