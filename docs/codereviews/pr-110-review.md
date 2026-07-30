# PR Review: #110 — fix: handle yaml boolean coercion with custom metamodel labels

**Reviewed**: 2026-07-30
**Author**: scartill
**Branch**: yaml-values-compare-raise-unexpected-report-erro → main
**Decision**: APPROVE

## Summary

Clean, well-scoped fix for issue #109. The helper `_yaml_value_to_str` is placed in the base `Extractor` class and correctly maps YAML 1.1 boolean coercion back to metamodel-defined labels. All three affected extractors are updated consistently. Test coverage is comprehensive.

## Findings

### CRITICAL
None

### HIGH
None

### MEDIUM

1. **Missing type annotation on `value` parameter** — `_yaml_value_to_str(self, value, atype: str, attr_name: str)` leaves `value` untyped. Since this method exists specifically to handle the `Any`-typed output of YAML parsing, an explicit `value: Any` (from `typing`) would be clearer and prevent linters from inferring `object`.
   - File: `src/syntagmax/extractors/extractor.py`, line 54

2. **Middle branch in markdown extractor still uses `str(value)` without coercion** — In `markdown.py` line 540, the `elif self._is_multiple_attr(...)` branch splits on commas using `str(value)`. For booleans, `str(True)` → `"True"` which has no comma, so the branch is never taken for boolean values — not a functional bug, but the `str(value)` call is inconsistent with the pattern established in the adjacent branches. If a future refactor changes the condition logic, this could silently regress.
   - File: `src/syntagmax/extractors/markdown.py`, line 540

### LOW

1. **Seed spec included but no full spec** — `docs/seed/yaml-boolean-coercion.md` is added (appropriate for a bugfix), but there's no corresponding entry in `docs/specs/`. Given the simplicity of the fix this is acceptable, but noted for traceability.

2. **Test imports `ObsidianExtractor` but fixture uses driver `'obsidian'`** — The test file imports `from syntagmax.extractors.obsidian import ObsidianExtractor`. The import path uses the `obsidian` module directly. This works, but the existence of both `markdown.py` and `obsidian.py` modules (where `ObsidianExtractor` lives in the obsidian module but extends the markdown extractor) could confuse future readers. A brief comment would help.

## Validation Results

| Check | Result |
|---|---|
| Type check | Skipped (no type-check configured) |
| Lint (ruff) | Pass |
| Tests | Pass (929/929) |
| Build | Skipped |

## Files Reviewed
| File | Status |
|---|---|
| `docs/seed/yaml-boolean-coercion.md` | Added |
| `src/syntagmax/extractors/extractor.py` | Modified |
| `src/syntagmax/extractors/markdown.py` | Modified |
| `src/syntagmax/extractors/sidecar.py` | Modified |
| `src/syntagmax/extractors/simple_markdown.py` | Modified |
| `tests/test_yaml_boolean_coercion.py` | Added |
