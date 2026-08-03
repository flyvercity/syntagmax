# PR Review: #120 — fix: prevent duplicate error records for missing parents

**Reviewed**: 2026-08-03
**Author**: scartill
**Branch**: similar-trace-error-records-in-analyze-report → main
**Decision**: APPROVE

## Summary

Clean, minimal fix that removes the redundant "Missing parent" error from `build_tree()` in favour of the more descriptive validation error already produced by `ArtifactValidator` in `analyse.py`. The structural tree-building logic remains intact.

## Findings

### CRITICAL
None

### HIGH
None

### MEDIUM
None

### LOW

1. **Unreachable branch after removal** — The `if suppress:` block on line 126 now only logs a warning when `suppress_tracing` is true, but does nothing when it's false (the `if pid not in full_set` body is empty in the non-suppress case). This is functionally correct but leaves a slightly odd control flow where the non-suppress path is a silent no-op. Cosmetic only; no action required since it doesn't affect behaviour and keeps the code symmetric with the suppress path.

## Validation Results

| Check | Result |
|---|---|
| Type check | Skipped |
| Lint (ruff) | Pass |
| Tests (pytest) | Pass (929 passed) |
| Build | Skipped |

## Files Reviewed

| File | Change |
|---|---|
| `src/syntagmax/tree.py` | Modified (2 lines removed) |
