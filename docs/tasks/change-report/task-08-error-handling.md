# [ ] Task 8: Error Handling and Fallback

## Objective

Implement graceful error handling throughout the change report pipeline, ensuring that extraction failures for individual files produce fallback plain-text diff output rather than aborting the entire report.

## Target Files

- `src/syntagmax/change_extract.py` (add error handling around extraction)
- `src/syntagmax/change_diff.py` (add fallback diff logic)
- `src/syntagmax/change_render.py` (add error section rendering)

## Dependencies

- **Task 2** (block extraction)
- **Task 3** (file diff)
- **Task 6** (renderer — needs to support error sections)

## Implementation

### Error Categories

1. **Invalid revision** — revision string does not resolve to any commit
   - Handled in Task 1's `resolve_revision()`
   - Raises `FatalError` with message like: `Revision "xyz" does not exist in the repository`

2. **File absent in one revision** — file exists in one revision but not the other
   - Already handled by file diff logic (Added/Removed status)
   - No special error handling needed

3. **Extraction failure** — extractor throws an exception for a specific file
   - Catch at the per-file level
   - Generate a fallback report section for that file

4. **Corrupted input** — malformed markdown that causes parser errors
   - Same as extraction failure — catch and fall back

### Fallback Mechanism

```python
@dataclass
class ExtractionError:
    file_path: str
    error_message: str
    base_content: str | None   # Raw file content at base revision
    target_content: str | None # Raw file content at target revision
```

When extraction fails for a file:

1. Catch the exception (broad `Exception` catch at per-file level)
2. Log the error with `lg.warning()`
3. Read raw file content from both revisions (plain `read_text()`)
4. Generate a plain-text diff using `difflib.unified_diff`
5. Store the error and raw diff in `ExtractionError`
6. Continue processing remaining files

### Fallback Diff

```python
def generate_fallback_diff(
    base_content: str | None,
    target_content: str | None,
    filepath: str,
) -> str:
```

- Uses `difflib.unified_diff(base_lines, target_lines, fromfile=filepath, tofile=filepath)`
- Returns the unified diff as a string
- If base_content is None (new file): show all lines as added
- If target_content is None (removed file): show all lines as removed

### Report Error Section

The renderer must handle `ExtractionError` entries and produce:

```markdown
### <filepath>

⚠️ **Extraction Error**

<error_message>

The following plain-text diff is provided as a fallback:

```diff
<unified diff output>
```
```

### Validation Errors (Pre-flight)

Before starting the pipeline:
- If config file doesn't exist → `FatalError`
- If not in a git repository → `FatalError`
- If `.syntagmax/worktrees/` not gitignored → `FatalError` with instructions
- If Git version < 2.5 → `FatalError`
- If both `--base` and `--target` are the same revision → warning (no changes expected)

### Partial Success

The command should:
- Process all files even if some fail extraction
- Report the number of failures in the summary section
- Exit with code 0 if at least one file was processed successfully
- Exit with code 1 only if ALL files failed or a fatal error occurred

## Technical Notes

- Use `try/except Exception` at the per-file extraction level (not too broad — keep `SystemExit` and `KeyboardInterrupt` propagating)
- Accumulate errors in a list that gets passed to the renderer
- The summary table should include a row: `| Extraction errors | N |` when N > 0
- Ensure worktree cleanup runs even on exceptions (already handled by context manager in Task 1)

## Test Requirements

- Test with an invalid revision → verify clear error message and exit code 1
- Test with a malformed markdown file that causes extraction to fail:
  - Verify the report still generates
  - Verify the error section appears with the fallback diff
  - Verify other files in the same record are processed normally
- Test with all files failing → verify exit code 1
- Test same base and target revision → verify warning message
- Test `generate_fallback_diff` with various inputs (both present, only base, only target)

## Test File

`tests/test_change_error_handling.py`
