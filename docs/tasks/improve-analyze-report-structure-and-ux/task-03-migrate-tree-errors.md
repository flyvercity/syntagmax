# [x] Task 3: Migrate Error Sites in `tree.py`

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

Replace string error appends in `tree.py` with `ReportError` objects.

## Dependencies

- Task 1 (ReportError dataclass must exist)

## Implementation

### `src/syntagmax/tree.py`

- Import `ReportError`, `CAT_REFERENCE`, `CAT_STRUCTURE`.
- `populate_pids()` errors:
  - "Conflicting nominal revisions" → `ReportError(category=CAT_REFERENCE, input_record=a.record.name, artifact_id=a.aid, artifact_type=a.atype, file_path=...)`
  - "Error processing parent link" → `ReportError(category=CAT_REFERENCE, ...)`
- `build_tree()` errors:
  - "Missing parent" → `ReportError(category=CAT_REFERENCE, input_record=a.record.name, ...)`
  - "Circular reference" → `ReportError(category=CAT_STRUCTURE, input_record=artifacts[ref].record.name if applicable, ...)`

## Test Requirements

- Build tree with missing parent produces `ReportError` with `category=CAT_REFERENCE`.
- Circular reference produces `ReportError` with `category=CAT_STRUCTURE`.

## Demo

Tree-related errors carry correct category and input record metadata.

## Files Modified

- `src/syntagmax/tree.py`
- `tests/test_metamodel_pids.py` (adapt assertions if needed)
