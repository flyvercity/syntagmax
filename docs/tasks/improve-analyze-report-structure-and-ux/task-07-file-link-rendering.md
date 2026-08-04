# [ ] Task 7: File Link Rendering

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

Implement configurable file link rendering in error output.

## Dependencies

- Task 1 (ReportConfig with `path_as_links` and `wiki_links`)
- Task 6 (report template and `format_error` filter registration)

## Implementation

### `src/syntagmax/report.py`

- Add Jinja2 custom filter `format_error(error: ReportError, config: ReportConfig) -> str`:
  - If `config.path_as_links` is false: return `str(error)` (legacy format).
  - If `config.wiki_links` is true: render message with `[[relative_path]]` (no line anchor).
  - Otherwise: render message with `[filename](relative_path#L{start_line})`.
  - Path is relative to project root (stored in `error.file_path` which is already relative per `config.derive_path()`).
- Register the filter in `Report.render()` when creating the Jinja2 environment.

### Error Construction Sites

- Ensure `file_path` is set using `config.derive_path()` (already produces posix relative paths from base_dir — these are relative to project root).

## Test Requirements

- With `path_as_links=False`: output matches legacy format.
- With `path_as_links=True, wiki_links=True`: output contains `[[path/to/file.md]]`.
- With `path_as_links=True, wiki_links=False`: output contains `[file.md](path/to/file.md#L10)`.
- Errors without file_path render without link regardless of config.

## Demo

Set `[report] path_as_links = true` in example config; run analyze; report contains clickable links.

## Files Modified

- `src/syntagmax/report.py`
- `src/syntagmax/resources/report.j2` (use `format_error` filter)
