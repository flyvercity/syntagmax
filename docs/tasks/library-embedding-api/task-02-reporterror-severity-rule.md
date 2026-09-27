# [ ] Task 2: Add `severity` and `rule` to `ReportError`

**Spec:** `docs/specs/library-embedding-api.spec.md` (R2, part 1; critique X1)

## Objective

Extend the existing structured error model without changing any rendered output.

## Implementation

### `src/syntagmax/report.py`

- Add `severity: str = 'error'` (values `error | warning`) and `rule: str | None = None` to the `ReportError` dataclass (append after existing fields; prefer keyword construction to keep any positional callers stable).
- `ReportError.from_any(str)` sets `severity='error'` and leaves `rule=None`.
- `__str__` and `format_error` remain unchanged (severity/rule are not rendered).

## Test Requirements

- `ReportError('msg', category=CAT_STRUCTURE).severity == 'error'` and `.rule is None`.
- `format_error` output unchanged for a representative error (golden assertion).
- Existing `tests/test_report.py` / `tests/test_report_error.py` remain green.

## Demo

Existing report tests pass; a `ReportError` can carry `severity`/`rule`.

## Files Modified

- `src/syntagmax/report.py`
- `tests/test_report_error.py`, `tests/test_report.py`
