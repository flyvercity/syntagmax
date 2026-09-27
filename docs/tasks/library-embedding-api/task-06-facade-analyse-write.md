# [x] Task 6: `syntagmax.api` facade — analyse + write side

**Spec:** `docs/specs/library-embedding-api.spec.md` (R1, parts 6–7; critique X1, P1, E3)

**Depends on:** Task 3 (structured diagnostics), Task 4 (write seam), Task 5 (facade read).

## Objective

Structured analysis result and the write methods with capability introspection.

## Implementation (`src/syntagmax/api.py`)

- `@dataclass class Diagnostic`: `severity, artifact_id, rule, category, location, message`.
- **`ReportError → Diagnostic` mapping (X1):** `severity = e.severity`; `artifact_id = e.artifact_id`; `rule = e.rule or e.category`; `category = e.category`; `location = f'{e.file_path}:{e.line_range[0]}-{e.line_range[1]}'` when both present, else `e.file_path or ''`; `message = e.message`.
- `@dataclass class AnalysisResult`: `diagnostics: list[Diagnostic]`, `metrics`, `impact`.
- `Session.analyse() -> AnalysisResult`: run the analysis path (reuse `main.process('metrics', config)` or the internal steps), convert `Report.errors` → `Diagnostic`s, pass through `metrics`/`impact`.
- `Session.edit(aid, *, fields=None, body=None) -> ArtifactView` and `Session.create(...) -> ArtifactView`: resolve record/driver, obtain the extractor, call the R3 seam, `reload()`, then return the fresh `get(aid)` view (P1). `Session.delete(aid) -> None`.
- `Session.capabilities(driver_or_record: str | InputRecord) -> set[str]`: read the extractor's `WRITE_CAPABILITIES` (E3 — name matches R1.7).

## Test Requirements (`tests/test_api.py`)

- `analyse()` on a fixture with a known issue returns a `Diagnostic` with the expected `artifact_id`/`category`/`severity`, and `rule`/`location` populated per the mapping.
- `edit()` on an obsidian fixture changes a field and **returns the updated `ArtifactView`** (no separate `get()` needed).
- `edit()` on a non-obsidian driver raises `UnsupportedOperation`; `capabilities()` reports empty for it.

## Demo

Script: `open_project` → `analyse()` prints diagnostics → `edit()` an obsidian artifact → returned `ArtifactView` shows the change.

## Files Modified

- `src/syntagmax/api.py`
- `tests/test_api.py`
