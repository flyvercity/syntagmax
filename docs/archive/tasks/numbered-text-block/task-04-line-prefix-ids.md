# Task 4: Update line-prefix marker splitting to capture and validate IDs

## Objective

Modify `_split_line_prefix()` to parse, validate, and store the optional ID from line-prefix markers like `[COM note.1] paragraph text`.

## Context

The line-prefix pattern currently uses `(?:\s+\d+)?` to optionally match a numeric suffix (discarded). In the line-prefix format, the ID appears between the marker name and the `]`, with a space after `]` before content.

## Target File

`src/syntagmax/extractors/markdown.py` — method `_split_line_prefix()`

## Implementation

1. Update the regex:
   ```python
   prefix_pattern = re.compile(
       rf'^\[({escaped})(?:\s+([^\]]+))?\]\s*(.*?)(?=\n\n|\Z)',
       re.IGNORECASE | re.DOTALL | re.MULTILINE,
   )
   ```
   Change: `(?:\s+\d+)?` → `(?:\s+([^\]]+))?` (capturing group for ID)

2. After matching, if group(2) is present:
   - Strip whitespace, call `_validate_block_id(id_str)`
   - If invalid → `ErrorBlock`
   - If valid → `TextBlock(..., id=id_str, explicit_id=True)`

3. If group(2) is None:
   - Call `generate_block_id(marker, content, filepath)`
   - Create `TextBlock(..., id=generated_id, explicit_id=False)`

4. Method signature changes to accept `filepath: str` parameter.

## Acceptance Criteria

1. `[COM note.1] paragraph text\n\n` → `TextBlock(id='note.1', marker='COM', explicit_id=True)`
2. `[COM] paragraph text\n\n` → `TextBlock(id=<hash>, marker='COM', explicit_id=False)`
3. `[COM inv@lid] text\n\n` → `ErrorBlock`
4. Multi-line continuation works: `[COM my_block] line1\nline2\n\n`
5. Existing line-prefix tests pass

## Dependencies

- Task 1, Task 6, Task 7, Task 9

## Parallelization

Cannot start until Tasks 1, 6, 7, 9 are complete. Can run in parallel with Tasks 2, 3.
