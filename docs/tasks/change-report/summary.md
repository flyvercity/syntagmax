# Change Report — Task Orchestration Summary

## Overview

This directory contains 10 implementation tasks for the `syntagmax change report` command.
Each task is self-contained with its own objective, implementation details, test requirements, and target files.

## Task List

| # | Task | Target File(s) | Status |
|---|------|---------------|--------|
| 1 | [Worktree Management](task-01-worktree-management.md) | `src/syntagmax/change_worktree.py` | [x] |
| 2 | [Block Extraction](task-02-block-extraction.md) | `src/syntagmax/change_extract.py` | [x] |
| 3 | [File-Level Diff](task-03-file-level-diff.md) | `src/syntagmax/change_diff.py` | [x] |
| 4 | [Artifact Comparison](task-04-artifact-comparison.md) | `src/syntagmax/change_diff.py` | [x] |
| 5 | [Text Block Comparison](task-05-text-block-comparison.md) | `src/syntagmax/change_diff.py` | [x] |
| 6 | [Markdown Renderer](task-06-markdown-renderer.md) | `src/syntagmax/change_render.py` | [x] |
| 7 | [CLI Wiring](task-07-cli-wiring.md) | `src/syntagmax/cli.py` | [x] |
| 8 | [Error Handling](task-08-error-handling.md) | multiple | [x] |
| 9 | [Integration Test](task-09-integration-test.md) | `tests/test_change_report.py` | [x] |
| 10 | [Documentation](task-10-documentation.md) | `README.md`, `docs/reference/` | [x] |

## Dependency Graph

```
Task 1 (Worktree)  ─────────────────────────────────────┐
                                                         │
Task 3 (File Diff) ──────────────────────────────────────┤
                                                         │
Task 2 (Extraction) ─── depends on Task 1               │
                                                         ├──► Task 7 (CLI Wiring)
Task 4 (Artifact Cmp) ── depends on Tasks 2, 3          │
                                                         │
Task 5 (Text Cmp) ────── depends on Tasks 2, 3          │
                                                         │
Task 6 (Renderer) ────── depends on Tasks 3, 4, 5       │
                         (data models only)              │
                                                         │
Task 8 (Error Handling) ─ depends on Tasks 2, 3, 6 ─────┘

Task 9 (Integration) ─── depends on ALL tasks 1-8

Task 10 (Docs) ────────── depends on Task 7 (can draft early)
```

## Parallel Execution Strategy

### Wave 1 (No dependencies — start immediately)

| Task | Notes |
|------|-------|
| **Task 1** | Standalone git worktree utilities |
| **Task 3** | Standalone git diff logic (only uses GitPython) |
| **Task 6** | Can define data model interfaces and implement rendering against test fixtures without waiting for actual diff logic |

### Wave 2 (After Wave 1 completes)

| Task | Requires |
|------|----------|
| **Task 2** | Task 1 (needs worktree paths) |
| **Task 4** | Tasks 2 + 3 (needs extracted blocks + diff module to extend) |
| **Task 5** | Tasks 2 + 3 (needs extracted blocks + diff module to extend) |

Note: Tasks 4 and 5 both extend `change_diff.py` from Task 3. If implementing in parallel, coordinate on the shared file or implement in separate functions that are later merged.

### Wave 3 (After Wave 2 completes)

| Task | Requires |
|------|----------|
| **Task 7** | Tasks 1-6 (integrates all components) |
| **Task 8** | Tasks 2, 3, 6 (adds error paths to existing code) |

Note: Task 8 can start as soon as Tasks 2, 3, and 6 are done. It modifies the same files but focuses on error paths.

### Wave 4 (After Wave 3 completes)

| Task | Requires |
|------|----------|
| **Task 9** | All of 1-8 (full pipeline test) |
| **Task 10** | Task 7 (needs final CLI interface) |

Tasks 9 and 10 can run in parallel with each other.

## Shared Module Coordination

Three tasks (3, 4, 5) write to the same file `src/syntagmax/change_diff.py`:

- **Task 3** creates the file with `FileDiff`, `FileStatus`, and `get_changed_files()`
- **Task 4** adds `ArtifactDiff`, `ArtifactChange`, and `compare_artifacts()`
- **Task 5** adds `TextBlockDiff`, `TextFragmentChange`, and `compare_text_blocks()`

**Recommended approach:** Implement Task 3 first (creates the module), then Tasks 4 and 5 can be done in parallel as they add independent functions/classes to the same file.

## Critical Path

The shortest path to a working (minimal) implementation:

```
Task 1 → Task 2 → Task 4 → Task 6 → Task 7
   +
Task 3 ──────────┘
```

This gives: worktree setup → extraction → artifact comparison → rendering → CLI. Text block comparison (Task 5), error handling (Task 8), and integration tests (Task 9) can follow after the core path works.

## File Ownership

| Source File | Created By | Extended By |
|-------------|-----------|-------------|
| `src/syntagmax/change_worktree.py` | Task 1 | Task 8 (error paths) |
| `src/syntagmax/change_extract.py` | Task 2 | Task 8 (error paths) |
| `src/syntagmax/change_diff.py` | Task 3 | Tasks 4, 5 |
| `src/syntagmax/change_render.py` | Task 6 | Task 8 (error sections) |
| `src/syntagmax/cli.py` | — | Task 7 (add command group) |
| `tests/test_change_worktree.py` | Task 1 | — |
| `tests/test_change_extract.py` | Task 2 | — |
| `tests/test_change_diff.py` | Task 3 | Tasks 4, 5 |
| `tests/test_change_render.py` | Task 6 | — |
| `tests/test_change_report_cli.py` | Task 7 | — |
| `tests/test_change_error_handling.py` | Task 8 | — |
| `tests/test_change_report.py` | Task 9 | — |

## Completion Criteria

All tasks are complete when:
1. All `[ ]` marks are changed to `[x]` in individual task files
2. All unit tests pass: `uv run pytest tests/test_change_*.py -v`
3. End-to-end test passes: `uv run pytest tests/test_change_report.py -v`
4. Manual verification: `uv run syntagmax --cwd ./example/obsidian-driver change report --base HEAD~1 --target HEAD` produces a valid report
5. Documentation is updated and consistent with implementation
