# Task Summary: Library-First Embedding API for Syntagmax

**Spec:** `docs/specs/library-embedding-api.spec.md`
**Branch:** `gui-adaptations` (core changes; upstreamed manually later)
**Critique applied:** `docs/critiques/library-embedding-api.critique.md` (pass 1 — X1, X2, E1, E2, P1, E3, P2 folded into the tasks below)

## Overview

7 tasks delivering an additive, sanctioned in-process embedding surface (`syntagmax.api`) plus three supporting core capabilities: redirectable impact tasks (`impact.task_dir`), structured diagnostics converged on `ReportError`, and an obsidian-only driver write seam. The CLI is left working unchanged; git writes stay out of the core.

## Dependency Graph

```
Task 1 (impact.task_dir)         ── independent
Task 2 (ReportError +severity/+rule)
  └── Task 3 (converge diagnostic producers)
Task 4 (obsidian write seam)     ── independent
Task 5 (facade: read side)       ── independent
        │
Task 6 (facade: analyse + write) ← depends on Tasks 3, 4, 5
Task 7 (docs & changelog)        ← depends on Tasks 1–6 (finalise last)
```

## Parallel Execution Strategy

### Wave 1 (start immediately, all parallel)
- **Task 1** — `impact.task_dir` (`config.py`, `tasks.py`)
- **Task 2** — `severity`/`rule` on `ReportError` (`report.py`)
- **Task 4** — obsidian write seam (`errors.py`, `extractor.py`, `markdown.py`)
- **Task 5** — facade read side (`api.py` new)

These four touch disjoint files and have no interdependencies.

### Wave 2
- **Task 3** — converge diagnostic producers (after Task 2)

### Wave 3
- **Task 6** — facade analyse + write side (after Tasks 3, 4, 5)

### Wave 4
- **Task 7** — documentation & changelog (after Tasks 1–6)

## Verification

After all tasks complete:

```bash
uv run ruff check src/syntagmax/
uv run pytest tests/
```

Both must pass with zero errors/warnings. In particular, the golden-output tests from Task 3 must confirm CLI/report text is byte-identical to pre-change output.

## Key Files Touched

| File | Tasks |
|------|-------|
| `src/syntagmax/config.py` | 1 |
| `src/syntagmax/tasks.py` (+ `main.py` impact step) | 1 |
| `src/syntagmax/report.py` | 2 |
| `src/syntagmax/analyse.py`, `tree.py`, `metrics.py`, `impact.py` | 3 |
| `src/syntagmax/errors.py` | 4 |
| `src/syntagmax/extractors/extractor.py` | 4 |
| `src/syntagmax/extractors/markdown.py` (obsidian) | 4 |
| `src/syntagmax/api.py` (new) | 5, 6 |
| `README.md`, `docs/reference/embedding-api.md` (new), config reference, `CHANGELOG.md` | 7 |
| `tests/test_task_dir.py` (new) | 1 |
| `tests/test_report_error.py`, `test_report.py` | 2 |
| `tests/test_report_grouping.py`, `test_analyse.py` | 3 |
| `tests/test_write_seam.py` (new) | 4 |
| `tests/test_api.py` (new) | 5, 6 |

## Notes

- **Task 6 is the join point.** It is the only task depending on three others; keep it last before docs.
- **Task 3 risk is regression, not logic.** The golden-output tests are the safety net — write them *before* migrating producers so any drift in rendered text is caught immediately.
- **Task 4 is the highest-care task** (file mutation): atomic `tempfile` + `os.replace`, path-traversal validation against `root_dir`, and the multi-artifact vs sole-artifact deletion rule must all be covered, on Windows too.
- Git writes/worktrees/commits, non-obsidian write drivers, CLI-on-facade refactor, and auth/async are all **out of scope** (per brainstorm Q2/Q4 and the spec's Out-of-Scope section).
