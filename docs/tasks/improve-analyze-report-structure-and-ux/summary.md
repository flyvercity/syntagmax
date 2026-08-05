# Task Summary: Improve Analyze Report Structure and UX

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`  
**Issue:** [#122](https://github.com/flyvercity/syntagmax/issues/122)

## Overview

10 tasks to introduce structured error reporting with grouping by input record and category, configurable file links, and per-input metrics in the Syntagmax analyze report.

## Dependency Graph

```
Task 1 (ReportError + ReportConfig)
  ├── Task 2 (migrate extract.py)
  ├── Task 3 (migrate tree.py)
  ├── Task 4 (migrate analyse.py)
  │
  └── Task 5 (migrate main.py + metrics) ← depends on Tasks 2–4
        │
        └── Task 6 (grouping helper + template) ← depends on Task 5
              │
              ├── Task 7 (file link rendering)
              └── Task 8 (localisation)

Task 9 (documentation) ← depends on Tasks 1–8
Task 10 (integration tests) ← depends on Tasks 1–8
```

## Parallel Execution Strategy

### Wave 1 (start immediately)
- **Task 1** — foundation, no dependencies

### Wave 2 (after Task 1 completes)
- **Task 2** — migrate extract.py errors
- **Task 3** — migrate tree.py errors
- **Task 4** — migrate analyse.py errors

Tasks 2, 3, 4 can run **in parallel** since they modify different modules.

### Wave 3 (after Tasks 2–4 complete)
- **Task 5** — migrate main.py + per-input metrics

### Wave 4 (after Task 5 completes)
- **Task 6** — grouping helper + template rewrite

### Wave 5 (after Task 6 completes)
- **Task 7** — file link rendering
- **Task 8** — localisation updates

Tasks 7, 8 can run **in parallel**.

### Wave 6 (after Tasks 7–8 complete)
- **Task 9** — documentation
- **Task 10** — integration tests

Tasks 9, 10 can run **in parallel**.

## Verification

After all tasks complete:
```bash
uv run ruff check src/syntagmax/
uv run pytest tests/
```

Both must pass with zero errors/warnings.

## Key Files Touched

| File | Tasks |
|------|-------|
| `src/syntagmax/report.py` | 1, 5, 6, 7 |
| `src/syntagmax/config.py` | 1 |
| `src/syntagmax/extract.py` | 2 |
| `src/syntagmax/tree.py` | 3 |
| `src/syntagmax/analyse.py` | 4 |
| `src/syntagmax/main.py` | 5 |
| `src/syntagmax/metrics.py` | 5 |
| `src/syntagmax/resources/report.j2` | 6, 7 |
| `src/syntagmax/resources/locales/*/messages.po` | 8 |
| `README.md` | 9 |
| `docs/reference/configuration.md` | 9 |
| `tests/test_report.py` | 6, 10 |
| `tests/test_report_grouping.py` | 10 |
| `tests/test_artifact_validation.py` | 2, 10 |
| `tests/test_reference_validation.py` | 4, 10 |

## Notes

- Tasks 2–4 all modify `errors: list[str]` → `list[ReportError]` in different modules. Merge conflicts are unlikely since each touches a different file, but coordinate the shared `errors` list type in `main.py` (handled in Task 5).
- The `from_any()` defensive coercion ensures that if any extractor/plugin still emits a plain string, the pipeline won't crash. This gives a safety net during the migration.
- After Wave 5, run the full example analysis to visually verify the report structure before writing documentation.
