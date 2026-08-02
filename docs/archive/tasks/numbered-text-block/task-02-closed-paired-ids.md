# Task 2: Update closed paired marker splitting to capture and validate IDs

## Objective

Modify `_split_closed_paired()` in the markdown extractor to parse, validate, and store the optional ID from `[COM id]...[/COM]` syntax.

## Context

The closed paired pattern currently uses `rf'\[({escaped})\](.*?)\[/\1\]'` which captures only the marker name. The new format allows an optional ID after the marker: `[COM com-1]text[/COM]`.

## Target File

`src/syntagmax/extractors/markdown.py` — method `_split_closed_paired()`

## Implementation

1. Change the regex to capture any text in the ID slot:
   ```python
   paired_pattern = re.compile(
       rf'\[({escaped})(?:\s+([^\]]+))?\](.*?)\[/\1\]',
       re.IGNORECASE | re.DOTALL
   )
   ```

2. After matching, if group(2) is present (ID text):
   - Strip whitespace from the captured ID
   - Call `_validate_block_id(id_str)` (from Task 6)
   - If invalid: append `ErrorBlock` with message
   - If valid: create `TextBlock(content=..., marker=..., id=id_str, explicit_id=True)`

3. If group(2) is None (no ID provided):
   - Call `generate_block_id(marker, content, filepath)` (from Task 7)
   - Create `TextBlock(content=..., marker=..., id=generated_id, explicit_id=False)`

4. Method signature changes to accept `filepath: str` parameter (threaded from Task 9).

## Acceptance Criteria

1. `[COM com-1]text[/COM]` → `TextBlock(content='text', marker='COM', id='com-1', explicit_id=True)`
2. `[COM]text[/COM]` → `TextBlock(content='text', marker='COM', id=<8-char-hash>, explicit_id=False)`
3. `[COM invalid!id]text[/COM]` → `ErrorBlock` with descriptive message
4. Same content/marker/filepath always produces the same auto-generated ID
5. Existing tests for closed paired markers continue to pass (they just gain `id` fields)

## Dependencies

- Task 1 (TextBlock id field)
- Task 6 (validation helper)
- Task 7 (hash generation)
- Task 9 (filepath threading)

## Parallelization

Cannot start until Tasks 1, 6, 7, 9 are complete. Can run in parallel with Tasks 3, 4.
