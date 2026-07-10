# Non-Artifact Block Identification

## Problem Statement

Non-artifact text blocks (tagged with fragment markers like `[COM]`, `[NOTE]`) currently have no identity. They cannot be cross-referenced in published output. We need to allow optional IDs on these blocks so they can serve as anchors in published documents.

## Requirements

1. Fragment markers can carry an optional ID: `[COM com-1]text` or `[COM]text` (no ID)
2. IDs contain only `[a-zA-Z0-9_-.]` characters; invalid IDs produce extraction errors
3. If absent, the tool generates a deterministic UUID (based on marker + content + file path) so IDs are stable across runs
4. IDs must be unique within a given marker type across the entire project; duplicates are extraction errors
5. The existing `(?:\s+\d+)?` numeric-only pattern is replaced with the new alphanumeric ID format
6. Uniqueness validation happens in `build_block_tree()`
7. IDs are not surfaced in published output for now

## Syntax

No ID (default):

```text
[COM]This is a commentary block
```

With ID:

```text
[COM com-1]This is an identified commentary block
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ID format | Replaces old numeric-only `[MARKER N]` pattern | Alphanumeric IDs are more expressive and subsume the old numeric format |
| Uniqueness scope | Global per project, within a marker type | Enables cross-file referencing without ambiguity |
| Auto-generation | Deterministic (SHA-256 of marker + content + filepath) | Stable IDs across runs without user intervention |
| Uniqueness check location | `build_block_tree()` in `publish.py` | This is where all blocks are aggregated across all input records |
| Downstream usage | Publishing anchors only (for now) | Keeps scope minimal; tracing/impact can be added later |

## Affected Components

- `src/syntagmax/blocks.py` — `TextBlock` dataclass gains an `id` field
- `src/syntagmax/extractors/markdown.py` — all three marker-splitting passes (`_split_closed_paired`, `_split_unclosed_paired`, `_split_line_prefix`) and the fallback terminator regex in `_extract_blocks_from_markdown()`
- `src/syntagmax/publish.py` — `build_block_tree()` gains uniqueness validation
- `docs/reference/obsidian.md` — fragment markers documentation update

## Tasks

### Task 1: Add `id` field to `TextBlock` dataclass

- **Objective:** Extend `TextBlock` in `blocks.py` to carry an optional block ID.
- **Implementation:** Add `id: str | None = None` field to the `TextBlock` dataclass.
- **Test:** Existing tests continue to pass (default `id=None`); new unit test confirms the field exists and defaults correctly.

### Task 2: Update closed paired marker splitting to capture IDs

- **Objective:** Modify `_split_closed_paired()` to parse and capture the optional ID from `[COM id]...[/COM]`.
- **Implementation:** Change the regex from `\[({escaped})\]` to `\[({escaped})(?:\s+([a-zA-Z0-9_.\-]+))?\]` in the opening tag. Pass the captured ID to the `TextBlock` constructor.
- **Test:** `[COM com-1]text[/COM]` → `TextBlock(content='text', marker='COM', id='com-1')`; `[COM]text[/COM]` → `TextBlock(content='text', marker='COM', id=None)`.

### Task 3: Update unclosed paired marker splitting to capture IDs

- **Objective:** Modify `_split_unclosed_paired()` to parse and capture the optional ID.
- **Implementation:** Replace `(?:\s+\d+)?` with `(?:\s+([a-zA-Z0-9_.\-]+))?`. Pass captured ID to `TextBlock`.
- **Test:** `[COM my-id]content\n\n` → `TextBlock(id='my-id', marker='COM', ...)`.

### Task 4: Update line-prefix marker splitting to capture IDs

- **Objective:** Modify `_split_line_prefix()` to parse and capture the optional ID.
- **Implementation:** Same regex change as Task 3. Pass captured ID to `TextBlock`.
- **Test:** `[COM note.1] paragraph text\n\n` → `TextBlock(id='note.1', marker='COM', ...)`.

### Task 5: Update fallback terminator regex in `_extract_blocks_from_markdown()`

- **Objective:** The fallback terminator regex for fragment markers at BOL uses `(?:\s+\d+)?` — update to match the new ID format.
- **Implementation:** Replace `(?:\s+\d+)?` with `(?:\s+[a-zA-Z0-9_.\-]+)?` in the fallback pattern construction.
- **Test:** An artifact block terminated by `[COM some-id]` at BOL correctly terminates.

### Task 6: Add ID validation

- **Objective:** Validate that user-provided IDs match `[a-zA-Z0-9_-.]` only; produce extraction errors for invalid IDs.
- **Implementation:** Add a validation function called from all three splitting passes. Invalid IDs produce an `ErrorBlock` with an appropriate message.
- **Test:** `[COM invalid!id]text[/COM]` produces an `ErrorBlock`.

### Task 7: Add deterministic ID generation for blocks without explicit IDs

- **Objective:** When no ID is provided, generate a stable UUID from `sha256(marker + content + filepath)`.
- **Implementation:** Add a helper `generate_block_id(marker: str, content: str, filepath: str) -> str` returning the first 8 hex chars of the SHA-256 digest. Call from all three splitting passes when ID is None.
- **Test:** Same content/marker/filepath always produces the same ID; different inputs produce different IDs.

### Task 8: Add global uniqueness validation in `build_block_tree()`

- **Objective:** After all blocks are collected, check that no two TextBlocks with the same marker type share the same ID.
- **Implementation:** Modify `build_block_tree()` to return `(BlockTree, list[str])` (tree + errors). Iterate all TextBlocks, group by `(marker, id)`, report duplicates. Update callers in `cli.py`.
- **Test:** Two files with `[COM com-1]` produce a duplicate ID error; `[COM x]` and `[NOTE x]` do NOT conflict.

### Task 9: Thread file path context through the marker splitting pipeline

- **Objective:** The splitting methods need the file path to generate deterministic IDs.
- **Implementation:** Add `filepath` parameter to `_split_text_block_by_markers()` and propagate to sub-methods.
- **Test:** Covered by Task 7 tests (deterministic ID depends on filepath).

### Task 10: Update documentation

- **Objective:** Update `docs/reference/obsidian.md` fragment markers section.
- **Implementation:** Replace "numbered variants" documentation with new ID syntax. Document validation rules and auto-generation behavior.
