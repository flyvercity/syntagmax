# [x] Task 2: Migrate Error Sites in `extract.py` and `build_artifact_map`

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

Replace string error appends in `extract.py` with `ReportError` objects.

## Dependencies

- Task 1 (ReportError dataclass must exist)

## Implementation

### `src/syntagmax/extract.py`

- Import `ReportError`, `CAT_EXTRACTION`, `CAT_DUPLICATE`.
- In `extract()`: wrap `record_errors` from each extractor. Extractor errors are strings — wrap them as `ReportError(message=err, category=CAT_EXTRACTION, input_record=record.name)`.
- In `build_artifact_map()`:
  - "has no ID" → `ReportError(message=..., category=CAT_EXTRACTION, input_record=a.record.name if a.record else None, file_path=str(a.location), ...)`
  - "Duplicate artifact ID" → `ReportError(message=..., category=CAT_DUPLICATE, input_record=a.record.name if a.record else None, artifact_id=a.aid, artifact_type=a.atype, file_path=str(a.location), ...)`
- Update function signatures: `errors: list[str]` → `errors: list[ReportError]`.

## Test Requirements

- `build_artifact_map` with duplicate IDs produces `ReportError` with `category=CAT_DUPLICATE` and correct `input_record`.
- `build_artifact_map` with missing ID produces `ReportError` with `category=CAT_EXTRACTION`.
- `str(error)` still contains the expected substrings for existing test assertions (update `test_artifact_validation.py` to use `str(errors[0])`).

## Demo

Existing tests adapted and passing; errors carry structured metadata.

## Files Modified

- `src/syntagmax/extract.py`
- `tests/test_artifact_validation.py`
