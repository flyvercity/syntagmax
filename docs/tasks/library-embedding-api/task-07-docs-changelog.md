# [x] Task 7: Documentation & changelog

**Spec:** `docs/specs/library-embedding-api.spec.md` (R5)

**Depends on:** Tasks 1–6 (documents whatever has landed); finalise last.

## Objective

Make the new embedding surface discoverable and satisfy the docs-update requirement (README **and** reference pages).

## Implementation

- `README.md`: add an "Embedding Syntagmax as a library" section with the `open_project`/`Session` example.
- `docs/reference/embedding-api.md` (new): document the facade — `Options`, `Session` (`artifacts/get/query/search/analyse/edit/create/delete/capabilities/reload`), `ArtifactView`, `Diagnostic`, `AnalysisResult`, the per-driver capability model, obsidian-only write note, thread-safety and the `reload()` full-reparse trade-off, and the `ReportError → Diagnostic` mapping.
- Configuration reference page: document `impact.task_dir` (absolute vs relative; default = current `tasks_dir` behaviour).
- `CHANGELOG.md`: add an entry summarising the four capabilities (facade, structured diagnostics, obsidian write seam, `impact.task_dir`).

## Test Requirements

- Docs are accurate and consistent with the implemented API; internal links valid.

## Demo

The embedding reference page shows a complete, runnable example matching `tests/test_api.py`.

## Files Modified

- `README.md`
- `docs/reference/embedding-api.md` (new)
- `docs/reference/configuration.md` (or the relevant config reference page)
- `CHANGELOG.md`
