# Task 9: Thread file path context through the marker splitting pipeline

## Objective

Pass the file path into the marker splitting methods so they can generate deterministic short hashes.

## Context

The splitting pipeline is called from `_extract_blocks_from_markdown()` where `filepath` is already available. It needs to flow down through the call chain to all three splitting methods.

## Target File

`src/syntagmax/extractors/markdown.py`

## Implementation

1. Update `_split_text_block_by_markers()` signature:
   ```python
   def _split_text_block_by_markers(self, text_block: TextBlock, filepath: str) -> list[Block]:
   ```

2. Update `_apply_marker_pass()` signature:
   ```python
   def _apply_marker_pass(self, blocks: list[Block], splitter, escaped: str, filepath: str) -> list[Block]:
   ```
   Pass `filepath` when calling the splitter:
   ```python
   result.extend(splitter(block.content, escaped, filepath))
   ```

3. Update all three splitter methods:
   ```python
   def _split_closed_paired(self, content: str, escaped: str, filepath: str) -> list[Block]:
   def _split_unclosed_paired(self, content: str, escaped: str, filepath: str) -> list[Block]:
   def _split_line_prefix(self, content: str, escaped: str, filepath: str) -> list[Block]:
   ```

4. Update the call site in `_extract_blocks_from_markdown()`:
   ```python
   rel_path = self._config.derive_path(filepath)
   # ...
   split_blocks.extend(self._split_text_block_by_markers(block, rel_path))
   ```

## Acceptance Criteria

1. All splitting methods accept a `filepath` parameter
2. The filepath is the relative path (from `config.derive_path()`)
3. Existing tests pass (update calls to include filepath)
4. Same block in different files → different auto-generated IDs

## Dependencies

- Task 1 (TextBlock must have `id` field)

## Parallelization

Can start after Task 1. Should complete before Tasks 2, 3, 4. Can run in parallel with Tasks 5, 6, 7, 8.
