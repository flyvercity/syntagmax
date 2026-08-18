# PR Review: #156 — 🔍 Scrutineer: Remove dead update_artifact method

**Reviewed**: 2026-08-14
**Author**: scartill (via Jules)
**Branch**: jules-10676051892736187662-6d6e13bb → more-jules-joined
**Decision**: APPROVE

## Product & User Summary

- **The "Why" & "What"**: Removes the dead `update_artifact` (singular) method from the extractor class hierarchy. This method was never called externally — all renumbering uses `update_artifacts` (plural) and all attribute manipulation uses `update_artifact_attributes`. Removing it reduces cognitive load and eliminates a misleading API surface.
- **Key User-Facing & Behavioral Changes**: None. No CLI, config, or output behaviour changes.
- **Risk Assessment & Migration Notes**: Zero risk. The removed method had no external callers. Both concrete extractors (`MarkdownExtractor`, `TextExtractor`) already override `update_artifacts` with real implementations, so the base class `pass` body is never reached in practice.
- **Testing Hints for QA**:
  1. Run `syntagmax edit identification --all` on any example project — renumbering should work identically.
  2. Run `syntagmax edit attrs -s <section> -n status -l active` — attribute editing should be unaffected.

## Technical Summary

Straightforward dead code removal. The `update_artifact` singular method was a vestigial API that both concrete implementations trivially delegated back to `update_artifacts`. Removing it simplifies the class hierarchy without affecting any live code paths.

## Findings

### CRITICAL

None

### HIGH

None

### MEDIUM

None

### LOW

None

## Validation Results

| Check | Result |
|---|---|
| Type check | Skipped |
| Lint (ruff) | Pass (PR files) |
| Tests (pytest) | Pass — 1196 passed, 1 pre-existing failure (unrelated) |
| Build | Skipped (editable install) |

## Files Reviewed

| File | Status |
|---|---|
| `src/syntagmax/extractors/extractor.py` | Modified |
| `src/syntagmax/extractors/markdown.py` | Modified |
| `src/syntagmax/extractors/text.py` | Modified |
| `.jules/scrutineer.md` | Modified |
