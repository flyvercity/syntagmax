# Task 5: Update fallback terminator regex in `_extract_blocks_from_markdown()`

## Objective

Update the fallback terminator regex that detects fragment markers at BOL. Currently it uses `(?:\s+\d+)?` which only matches numeric suffixes. It must match the new alphanumeric ID format.

## Context

In `_extract_blocks_from_markdown()`, when an artifact block has no explicit `[/MARKER]` or YAML terminator, the code detects terminators at BOL: fragment markers, headings, or empty lines. The fragment marker pattern must recognize `[COM some-id]` as a valid terminator.

This task is independent of the ID capture/validation logic — it only needs to *recognize* the pattern for termination purposes.

## Target File

`src/syntagmax/extractors/markdown.py` — method `_extract_blocks_from_markdown()`

Find this line (around line 555):
```python
fallback_patterns.append(rf'^(?:\[(?:{escaped_markers})(?:\s+\d+)?\])')
```

## Implementation

Replace:
```python
fallback_patterns.append(rf'^(?:\[(?:{escaped_markers})(?:\s+\d+)?\])')
```

With:
```python
fallback_patterns.append(rf'^(?:\[(?:{escaped_markers})(?:\s+[^\]]+)?\])')
```

The pattern `[^\]]+` matches any characters except `]`, covering both valid and invalid IDs.

## Acceptance Criteria

1. Artifact block terminated by `[COM some-id]` at BOL → correct termination
2. Artifact block terminated by `[COM invalid!id]` at BOL → correct termination
3. Artifact block terminated by `[COM]` at BOL → existing behavior preserved
4. All existing fallback terminator tests pass
5. No regression in `[/MARKER]` or YAML terminators

## Dependencies

None — standalone regex update.

## Parallelization

Can run in parallel with all other tasks. No dependencies.
