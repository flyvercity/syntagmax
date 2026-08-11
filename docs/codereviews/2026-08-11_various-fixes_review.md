# Code Review: `various-fixes`

- **Date**: 2026-08-11
- **Target Branch**: `main`
- **Files Changed**: 13

## 1. Architectural & Design Overview

This PR introduces two main feature enhancements along with complete documentation and seed specs:
1. **Subdirectory Organization for CLI Outputs**: Organizes trace matrices under `<output_path>/trace/` and publish outputs under `<output_path>/publish/` (or `<output_path>/publish/published.md` for single output mode), preventing flat directory clutter in `.syntagmax/outputs/`.
2. **Configurable Cross-Input Duplicate Block ID Validation**: Refactors `publish` configuration handling in `config.toml` to support both string paths (legacy backward-compatible format) and a `[publish]` table with options. Introduces `cross_input_duplicates` (boolean, default `true`), allowing users with independent marker numbering across separate input records (e.g., `[COM 1]`) to scope duplicate validation per-input.

The overall architectural design is clean, backward compatible, and well-tested.

## 2. Security & Performance Audit

- **Security Concerns**: None. Output path construction uses `pathlib.Path` with safe directory creation (`mkdir(parents=True, exist_ok=True)`). No shell injection, secret exposure, or unsafe dynamic evaluations.
- **Performance & Scalability**: Minimal impact. Scoping duplicate block ID validation per-input resets the local tracking set `seen` between inputs, maintaining $O(N)$ time complexity where $N$ is the number of blocks.

## 3. Detailed File-by-File Findings

### `src/syntagmax/config.py`
- **[Severity: Medium]** Lines 204-209: The boolean coercer `coerce_cross_input_duplicates` silently returns `False` for any string not matching `('true', '1', 'yes')`.
  - **Context**: Passing an invalid string like `cross_input_duplicates = "invalid"` or a mistyped value like `"truee"` will silently evaluate to `False` without raising a validation error.
  - **Suggested Fix**:
    ```suggestion
    @field_validator('cross_input_duplicates', mode='before')
    @classmethod
    def coerce_cross_input_duplicates(cls, v):
        if isinstance(v, str):
            val = v.lower()
            if val in ('true', '1', 'yes'):
                return True
            if val in ('false', '0', 'no'):
                return False
            raise ValueError(f'Invalid boolean value for cross_input_duplicates: {v}')
        return v
    ```

### `src/syntagmax/publish.py`
- **[Severity: Low]** Lines 84-86: Per-input state reset logic in `build_block_tree`.
  - **Context**: The `seen` dictionary is reset per `InputBlock`. This correctly limits duplicate detection to individual input records while preserving intra-input duplicate detection across multiple files. The logic is concise and effective.

### `src/syntagmax/cli_tools.py` & `src/syntagmax/cli_publish.py`
- **[Severity: Low]** Default output path generation.
  - **Context**: Output paths correctly append `/trace` and `/publish` subpaths when `--output` is omitted, while respecting explicit user-provided output paths. CI workflow template generators in `cli_tools.py` have also been updated to reflect the new default paths.

## 4. Test Coverage & Edge Cases

- **Test Coverage**: Excellent. `tests/test_publish.py` includes comprehensive test cases covering `cross_input_duplicates` when enabled (default), disabled, intra-input duplicates, and legacy string configuration. `tests/test_ci_commands.py` tests have been updated for new default subpaths.
- **Edge Cases to Handle**:
  - Mistyped string values in TOML configuration for `cross_input_duplicates`.

## 5. Actionable Next Steps

- [x] Refactor `coerce_cross_input_duplicates` in `src/syntagmax/config.py` to raise `ValueError` on unrecognized string values rather than defaulting silently to `False`.
