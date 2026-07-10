# Task 8: Add global uniqueness validation in `build_block_tree()`

## Objective

After all blocks are collected in `build_block_tree()`, validate that no two TextBlocks with user-provided (explicit) IDs share the same ID within the same marker type.

## Context

`build_block_tree()` in `publish.py` aggregates blocks from all input records. Only **explicit** IDs are checked — auto-generated hashes are excluded to avoid false positives from identical blocks.

## Target Files

- `src/syntagmax/publish.py` — `build_block_tree()` function
- `src/syntagmax/cli.py` — callers of `build_block_tree()`

## Implementation

1. Change `build_block_tree()` return type:
   ```python
   def build_block_tree(config: Config) -> tuple[BlockTree, list[str]]:
   ```

2. After building the tree, validate explicit IDs:
   ```python
   errors: list[str] = []
   seen: dict[tuple[str, str], str] = {}  # (marker, id) -> first file path

   for input_block in tree.inputs:
       for file_record in input_block.files:
           for block in file_record.blocks:
               if isinstance(block, TextBlock) and block.explicit_id and block.id:
                   key = (block.marker, block.id)
                   if key in seen:
                       errors.append(
                           f'Duplicate block ID "{block.id}" for marker [{block.marker}] '
                           f'in {file_record.path} (first defined in {seen[key]})'
                       )
                   else:
                       seen[key] = file_record.path

   return tree, errors
   ```

3. Update callers in `cli.py` to unpack the tuple and handle errors.

## Acceptance Criteria

1. Two files with `[COM com-1]` (same marker, same explicit ID) → duplicate error
2. `[COM x]` and `[NOTE x]` (different markers, same ID) → NO conflict
3. Two files with `[COM]` and identical content (same hash) → NO conflict
4. `build_block_tree()` returns `(BlockTree, list[str])`
5. Callers in `cli.py` updated
6. Existing publish tests updated to unpack tuple

## Dependencies

- Task 1 (TextBlock `id` and `explicit_id` fields)

## Parallelization

Can start after Task 1. Can run in parallel with Tasks 2–7, 9.
