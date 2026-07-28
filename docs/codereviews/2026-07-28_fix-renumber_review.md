# Code Review: [fix-renumber]
- **Date**: 2026-07-28
- **Target Branch**: `main`
- **Files Changed**: 14

## 1. Architectural & Design Overview
This branch implements a two-pass non-destructive renumbering algorithm that preserves existing, valid IDs in targeted files instead of unconditionally overwriting them. 

The architecture is sound and well-structured:
1. **Utility Extraction**: The regex compilation and numeric ID extraction logic is abstracted into a clean, centralized helper module `src/syntagmax/id_utils.py`, which is imported by both `src/syntagmax/analyse.py` and `src/syntagmax/edit.py`. This prevents code duplication.
2. **Two-Pass Algorithm**: `src/syntagmax/edit.py` implements Pass 1 (max number extraction) and Pass 2 (new ID assignment). Pass 1 dynamically checks current IDs against resolved schemas, extracts sequential numbers, and tracks the maximum value. Pass 2 uses these numbers to safely assign new sequential IDs from `max_number + 1` for missing/templated IDs without overwriting conforming ones.
3. **Metamodel Validation**: Validates at load time that schemas contain at most 1 `{num}` macro.
4. **Command Changes**: Removes the redundant `--schema` CLI option and adds a `--force` flag to let users override the preservation behavior and renumber everything starting from 1.

## 2. Security & Performance Audit
- **Security Concerns**: None. Regular expressions compiled from schemas are validated, anchored, and use simple digits/character matching, which protects against ReDoS (Regular Expression Denial of Service).
- **Performance & Scalability**: The two-pass algorithm correctly loops over the list of targeted artifacts twice ($O(N)$ time complexity). Caching of compiled ID schema regexes prevents redundant recompilations, ensuring high performance even when processing large projects with thousands of artifacts.

## 3. Detailed File-by-File Findings

### `src/syntagmax/id_utils.py`
- **[Severity: Medium]** Line 55-61: Potential `IndexError` if a schema contains zero `{num}` macros (fixed-ID singletons).
  - **Context**: If a schema has zero `{num}` macros (e.g. `REQ-FIXED`), `compile_id_schema` will produce a pattern without any capturing groups (e.g., `^REQ\-FIXED$`). When `extract_number_from_id` matches an ID against this pattern, `m.group(1)` will fail with `IndexError: no such group`. Although `edit.py` filters out zero-macro schemas during renumbering, `extract_number_from_id` should be robust on its own to prevent unexpected crashes in other integration points.
  - **Suggested Fix**:
    ```suggestion
    def extract_number_from_id(aid: str, schema: str, atype: str) -> int | None:
        """Match aid against the compiled schema and return the extracted number, or None."""
        compiled = compile_id_schema(schema, atype)
        m = compiled.match(aid)
        if m and m.groups():
            return int(m.group(1))
        return None
    ```

### `src/syntagmax/edit.py`
- **[Severity: Low]** Line 80-87: Exit codes/unhandled return status on abort.
  - **Context**: If `renumber_artifacts` aborts because a schema has multiple `{num}` macros, it logs an error and returns `None` immediately. The CLI command exits with code `0`. To be a robust CLI tool, it should signal failure (either by returning `False` or raising an exception) so that the CLI runner exits with a non-zero status code.
  - **Suggested Fix**:
    Have `renumber_artifacts` return `False` or raise `FatalError` when validation fails, and have the command handler exit accordingly.

## 4. Test Coverage & Edge Cases
- **Missing Tests**: Coverage is extremely thorough (914 tests passing). There are tests for dry-runs, forces, per-type counters, padding, duplicate IDs, zero `{num}` macros, and multiple `{num}` macros.
- **Edge Cases to Handle**: 
  - Ensure the utility behaves gracefully when schemas with zero `{num}` macros are checked (as described in the `IndexError` finding).
  - Handle potential non-integer matching characters in ID templates if schemas ever relax digit restrictions (currently safe because regex generates `\d`).

## 5. Actionable Next Steps
- [ ] Implement `IndexError` protection in `extract_number_from_id` (High Priority).
- [ ] Add return statuses to `renumber_artifacts` and exit codes to CLI commands upon execution failures (Low Priority).
