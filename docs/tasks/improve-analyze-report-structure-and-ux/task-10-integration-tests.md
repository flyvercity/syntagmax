# [x] Task 10: Integration Tests

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

End-to-end tests covering the full report pipeline with structured errors, grouping, and link rendering.

## Dependencies

- Tasks 1–8 (all implementation complete)

## Implementation

### `tests/test_report_grouping.py` (new)

- Test: multiple errors from different inputs group correctly in rendered output.
- Test: global errors appear under "Global" heading.
- Test: single input record produces aggregate metrics only.
- Test: multiple input records produce aggregate metrics + per-input metrics subsections.
- Test: `path_as_links=True, wiki_links=False` produces Markdown links in output.
- Test: `path_as_links=True, wiki_links=True` produces wiki links in output.
- Test: `path_as_links=False` produces plain text paths (backward compat).
- Test: plain string errors mixed with `ReportError` objects do not crash rendering.
- Test: categories render in `CANONICAL_CATEGORY_ORDER`.
- Test: `--warnings-as-errors` CLI flag correctly triggers `FatalError` when `ReportError` instances are present.

### `tests/test_report.py` (update)

- Adapt existing tests to use `ReportError` objects instead of strings.
- Verify backward compatibility of `__str__`.

### `tests/test_artifact_validation.py`, `tests/test_reference_validation.py` (update)

- Assertions use `str(errors[0])` where testing string content, or check `.category` / `.input_record` fields for structured assertions.

## Test Requirements

All tests pass; no regressions.

## Demo

Full test suite green; `pytest tests` passes with no warnings.

## Files Modified

- `tests/test_report_grouping.py` (new)
- `tests/test_report.py`
- `tests/test_artifact_validation.py`
- `tests/test_reference_validation.py`
