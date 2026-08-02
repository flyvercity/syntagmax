# Task 3: Update unclosed paired marker splitting to capture and validate IDs

## Objective

Modify `_split_unclosed_paired()` to parse, validate, and store the optional ID, and update the lookahead termination logic to recognize alphanumeric IDs.

## Context

The unclosed paired pattern currently uses `(?:\s+\d+)?` to optionally match a numeric suffix (discarded). The lookahead pattern that terminates unclosed blocks also uses this numeric-only pattern. Both must be updated.

## Target File

`src/syntagmax/extractors/markdown.py` — method `_split_unclosed_paired()`

## Implementation

1. Update the main regex to capture any text in the ID position:
   ```python
   unclosed_pattern = re.compile(
       rf'\[({escaped})(?:\s+([^\]]+))?\](.*?)(?=\n\s*\n|\n\s*\[(?:{escaped})(?:\s+[^\]]+)?\]|\n\s*#{{1,6}}\s|\Z)',
       re.IGNORECASE | re.DOTALL,
   )
   ```
   Key changes:
   - `(?:\s+\d+)?` → `(?:\s+([^\]]+))?` (capturing group for ID)
   - Lookahead: `(?:\s+\d+)?` → `(?:\s+[^\]]+)?` (matches any ID format)

2. After matching, if group(2) is present:
   - Strip whitespace, call `_validate_block_id(id_str)`
   - If invalid → `ErrorBlock`
   - If valid → `TextBlock(..., id=id_str, explicit_id=True)`

3. If group(2) is None:
   - Call `generate_block_id(marker, content, filepath)`
   - Create `TextBlock(..., id=generated_id, explicit_id=False)`

4. Method signature changes to accept `filepath: str` parameter.

## Acceptance Criteria

1. `[COM my-id]content\n\n` → `TextBlock(id='my-id', marker='COM', explicit_id=True)`
2. `[COM]content\n\n` → `TextBlock(id=<hash>, marker='COM', explicit_id=False)`
3. `[COM bad!]content\n\n` → `ErrorBlock`
4. Lookahead terminates correctly when followed by `[COM next-id]`
5. Existing unclosed paired tests pass

## Dependencies

- Task 1, Task 6, Task 7, Task 9

## Parallelization

Cannot start until Tasks 1, 6, 7, 9 are complete. Can run in parallel with Tasks 2, 4.
