# [x] Task 3: Converge diagnostic producers on structured `ReportError`

**Spec:** `docs/specs/library-embedding-api.spec.md` (R2, part 2; critique X1)

**Depends on:** Task 2 (`severity`/`rule` fields must exist first).

## Objective

Make structured errors the single source of truth; derive human strings from them; no parallel channel (Q3: "no duplication").

## Implementation

- Inventory the ~53 `errors.append(...)` sites (17 in `analyse.py`, plus `tree.py`, `metrics.py`, `impact.py`, `extract.py`, `metamodel.py`, `config.py`).
- For each site that appends a **bare string** and has context (artifact id/type, file, category), construct a `ReportError(...)` instead — populating `artifact_id`/`artifact_type`/`file_path`/`category`/`severity` where available, and `rule` when a rule id exists.
- Prioritise `analyse.py`, `tree.py`, `metrics.py`, `impact.py` (these feed the Analysis view). Load-time errors in `metamodel.py`/`config.py` may stay string-coerced via `from_any` (still one channel).
- Do **not** introduce a second list; keep appending to the same `errors` list that becomes `Report.errors`.

## Test Requirements

- **Golden-output tests:** capture current `report.render()` output for representative fixtures (reuse `tests/test_report_grouping.py` fixtures) and assert byte-identical after migration.
- New assertions that migrated errors carry `artifact_id`/`category`/`severity` where applicable.

## Demo

`uv run pytest tests/test_report.py tests/test_report_grouping.py tests/test_analyse.py` green; a schema error now exposes a populated `artifact_id`.

## Files Modified

- `src/syntagmax/analyse.py`, `src/syntagmax/tree.py`, `src/syntagmax/metrics.py`, `src/syntagmax/impact.py` (and other prioritised producers)
- `tests/test_report_grouping.py`, `tests/test_analyse.py`
