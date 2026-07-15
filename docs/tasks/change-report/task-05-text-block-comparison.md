# [x] Task 5: Text Block Comparison (Non-Artifact)

## Objective

Add text fragment diffing logic to `change_diff.py` that compares `TextBlock` instances between base and target revisions for the same file.

## Target File

`src/syntagmax/change_diff.py` (extends the file from Tasks 3 & 4)

## Dependencies

- **Task 2** (block extraction — provides `list[FileRecord]` with `TextBlock` instances)
- **Task 3** (file diff — provides `change_diff.py` module and `FileDiff` for file matching)

## Implementation

### Data Model

```python
@dataclass
class TextFragmentChange:
    status: FileStatus           # Added, Removed, Modified
    file_path: str               # File the fragment belongs to
    old_content: str | None      # Content in base revision (None if added)
    new_content: str | None      # Content in target revision (None if removed)
    old_lines: tuple[int, int] | None   # Line range in base (start, end)
    new_lines: tuple[int, int] | None   # Line range in target (start, end)
    marker: str | None           # Fragment marker type (COM, NOTE, etc.) if present


@dataclass
class TextBlockDiff:
    added: list[TextFragmentChange]
    removed: list[TextFragmentChange]
    modified: list[TextFragmentChange]
```

### Main Function

```python
def compare_text_blocks(
    base_records: list[FileRecord],
    target_records: list[FileRecord],
) -> TextBlockDiff:
```

### Algorithm

1. **Group text blocks by file path:**
   - For each file present in both base and target records, collect `TextBlock` instances in order

2. **Match blocks within a file:**
   - Use `difflib.SequenceMatcher` on block content strings to align base and target blocks
   - Matching is positional + content-similarity based

3. **Performance guard:**
   - If a text block exceeds 200 lines, skip `SequenceMatcher` for that block
   - Fall back to `difflib.unified_diff` for line-by-line comparison
   - Report the entire block as modified with line ranges

4. **Classify results:**
   - Unmatched base blocks → Removed
   - Unmatched target blocks → Added
   - Matched pairs with different content → Modified

5. **Compute line ranges:**
   - Derive line numbers from `source_offset` attribute on `TextBlock` (character offset of the block in the source file)
   - Convert character offset to line number by counting newlines in the file content up to that offset
   - If `source_offset` is None, fall back to sequential position estimation

### Files only in one revision

- If file exists only in target: all its text blocks are "Added"
- If file exists only in base: all its text blocks are "Removed"

## Technical Notes

- `TextBlock.content` is the raw text content of the block
- `TextBlock.marker` may be set (e.g., `COM`, `NOTE`) for marked fragments
- `TextBlock.id` can help with matching if explicit IDs are present (prefer ID-based matching over positional when available)
- `TextBlock.source_offset` provides the character offset in the original file for line range computation
- Marked text blocks with explicit IDs should be matched by ID (like artifacts), falling back to positional matching only for unmarked blocks

## Test Requirements

- Create mock `FileRecord` lists with `TextBlock` instances
- Test: text block present only in target → classified as added with `new_lines`
- Test: text block present only in base → classified as removed with `old_lines`
- Test: text block in both with different content → classified as modified with both line ranges
- Test: text block in both with same content → NOT in any change list
- Test: large block (>200 lines) triggers fallback behavior
- Test: marked blocks with explicit IDs matched by ID
- Test: unmarked blocks matched by position/content similarity

## Test File

`tests/test_change_diff.py` (extends from Tasks 3 & 4)
