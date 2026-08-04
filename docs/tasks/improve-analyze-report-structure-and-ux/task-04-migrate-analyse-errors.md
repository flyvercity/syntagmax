# [ ] Task 4: Migrate Error Sites in `analyse.py` (ArtifactValidator)

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

Replace all `self.errors.append(str)` calls in `ArtifactValidator` with `ReportError` objects.

## Dependencies

- Task 1 (ReportError dataclass must exist)

## Implementation

### `src/syntagmax/analyse.py`

- Import `ReportError`, `CAT_SCHEMA`, `CAT_ATTRIBUTE`, `CAT_REFERENCE`, `CAT_TRACE`, `CAT_STRUCTURE`.
- Add helper `_make_error(self, artifact, message, category)` that constructs `ReportError` with artifact's record, ID, type, file path, and line range extracted from `artifact.location`.
- Replace each `self.errors.append(f"...")` with `self.errors.append(self._make_error(artifact, message, category))`:
  - `_validate_id_schema` → `CAT_SCHEMA`
  - `_check_extra_attributes` → `CAT_ATTRIBUTE`
  - `_check_attribute_requirements` (missing mandatory) → `CAT_ATTRIBUTE`
  - `_check_type` (integer, boolean, enum) → `CAT_ATTRIBUTE`
  - `_check_type` (reference — unknown ID, unknown type) → `CAT_REFERENCE`
  - `_validate_traces` (forbidden trace, mode violation, missing mandatory trace) → `CAT_TRACE`
  - "Unknown artifact type" → `CAT_ATTRIBUTE`
- `analyse_tree()` "Must have exactly one root" → `ReportError(category=CAT_STRUCTURE, input_record=None)`

## Test Requirements

- Validator produces `ReportError` objects with correct categories.
- `str(error)` matches legacy format for existing tests in `test_artifact_validation.py`, `test_reference_validation.py`, `test_traces.py`.
- Tests in `test_id_validation.py` adapted.

## Demo

All validation errors carry structured metadata; existing test assertions pass via `str()`.

## Files Modified

- `src/syntagmax/analyse.py`
- `tests/test_artifact_validation.py` (adapt assertions)
- `tests/test_reference_validation.py` (adapt assertions)
- `tests/test_traces.py` (adapt assertions)
- `tests/test_id_validation.py` (adapt assertions)
