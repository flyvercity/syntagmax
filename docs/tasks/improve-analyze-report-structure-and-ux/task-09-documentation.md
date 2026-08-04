# [ ] Task 9: Documentation Update

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

Update README.md and `docs/reference/configuration.md` with the new `[report]` section and updated report structure description.

## Dependencies

- Tasks 1–8 (all implementation complete — documentation reflects final behaviour)

## Implementation

### `README.md`

- Update "Report Output" section to describe the new grouped structure.
- Add `[report]` section documentation with examples:
  ```toml
  [report]
  path_as_links = true
  wiki_links = false
  ```
- Show example output snippets with grouped errors.

### `docs/reference/configuration.md`

- Add `[report]` section reference with field descriptions, defaults, and examples.
- Document link rendering behaviour:
  - Wiki links: `[[path/to/file.md]]` — no line anchors
  - Standard Markdown links: `[file.md](path/to/file.md#L10)` — with line anchors
  - Path relativity: relative to project root (working directory)
- Document that `wiki_links` is only relevant when `path_as_links = true`.

## Test Requirements

N/A (documentation only).

## Demo

Documentation accurately reflects the new report capabilities.

## Files Modified

- `README.md`
- `docs/reference/configuration.md`
