# Non-Artifact Block Identification

## Problem Statement

Non-artifact text blocks (tagged with fragment markers like `[COM]`, `[NOTE]`) currently have no identity. They cannot be cross-referenced in published output. We need to allow optional IDs on these blocks so they can serve as anchors in published documents.

## Requirements

1. Fragment markers can carry an optional ID: `[COM com-1]text` or `[COM]text` (no ID)
2. IDs contain only `[a-zA-Z0-9_-.]` characters; invalid IDs produce extraction errors
3. If absent, the tool generates a deterministic short hash (first 8 hex chars of SHA-256 of marker + content + file path) for internal tracking.
4. User-provided (explicit) IDs must be unique within a given marker type across the entire project; duplicates are extraction errors. Auto-generated IDs are not validated for uniqueness.
5. The existing `(?:\s+\d+)?` numeric-only pattern is replaced with the new alphanumeric ID format
6. Uniqueness validation of explicit IDs happens in `build_block_tree()`
7. Explicit block IDs are not surfaced in published output for now (downstream usage is deferred).

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
| Uniqueness scope | Global per project, within a marker type, explicit IDs only | Enables cross-file referencing without ambiguity; auto-generated hashes are excluded to avoid false positives from identical blocks |
| Auto-generation | Deterministic short hash (first 8 hex chars of SHA-256) | Stable IDs across runs for internal tracking without user intervention |
| Uniqueness check location | `build_block_tree()` in `publish.py` | This is where all blocks are aggregated across all input records |
| Downstream usage | Publishing anchors only (deferred) | Keeps scope minimal; tracing/impact can be added later |
| Regex strategy | Capture any text in ID slot, validate in Python | Ensures invalid IDs produce errors rather than silently falling through as unmarked text |

## Affected Components

- `src/syntagmax/blocks.py` — `TextBlock` dataclass gains an `id` field
- `src/syntagmax/extractors/markdown.py` — all three marker-splitting passes (`_split_closed_paired`, `_split_unclosed_paired`, `_split_line_prefix`) and the fallback terminator regex in `_extract_blocks_from_markdown()`
- `src/syntagmax/publish.py` — `build_block_tree()` gains uniqueness validation
- `docs/reference/obsidian.md` — fragment markers documentation update

## Tasks

### Task 1: Add `id` field to `TextBlock` dataclass

- **Objective:** Extend `TextBlock` in `blocks.py` to carry an optional block ID and track whether it was explicitly provided.
- **Implementation:** Add `id: str | None = None` and `explicit_id: bool = False` fields to the `TextBlock` dataclass. `explicit_id` is `True` when the user wrote an ID in the source; `False` for auto-generated short hashes.
- **Test:** Existing tests continue to pass (default `id=None`, `explicit_id=False`); new unit test confirms the fields exist and default correctly.

### Task 2: Update closed paired marker splitting to capture and validate IDs

- **Objective:** Modify `_split_closed_paired()` to parse and validate the optional ID.
- **Implementation:** Change the regex to match any text within the opening tag: `rf'\[({escaped})(?:\s+([^\]]+))?\](.*?)\[/\1\]'`. In Python code, if the ID is present, validate that it matches `^[a-zA-Z0-9_.\-]+$`. If invalid, return an `ErrorBlock` with the message. Otherwise, pass the validated ID to the `TextBlock`.
- **Test:** `[COM com-1]text[/COM]` → `TextBlock(id='com-1')`; `[COM invalid!id]text[/COM]` → `ErrorBlock`.

### Task 3: Update unclosed paired marker splitting to capture and validate IDs

- **Objective:** Modify `_split_unclosed_paired()` to parse and validate the optional ID, and update lookahead logic.
- **Implementation:** Change the regex to match any text in the ID portion, e.g. `rf'\[({escaped})(?:\s+([^\]]+))?\]'`. Update the termination lookahead regex to match `\n\s*\[(?:{escaped})(?:\s+[^\]]+)?\]` so alphanumeric IDs also terminate preceding unclosed blocks. Validate the captured ID in Python; if invalid, return `ErrorBlock`.
- **Test:** `[COM my-id]content\n\n` → `TextBlock(id='my-id')`; lookahead terminates correctly when followed by `[COM next-id]`.

### Task 4: Update line-prefix marker splitting to capture IDs

- **Objective:** Modify `_split_line_prefix()` to parse and capture the optional ID.
- **Implementation:** Same regex change as Task 3. Pass captured ID to `TextBlock`.
- **Test:** `[COM note.1] paragraph text\n\n` → `TextBlock(id='note.1', marker='COM', ...)`.

### Task 5: Update fallback terminator regex in `_extract_blocks_from_markdown()`

- **Objective:** The fallback terminator regex for fragment markers at BOL uses `(?:\s+\d+)?` — update to match alphanumeric IDs.
- **Implementation:** Replace `(?:\s+\d+)?` with `(?:\s+[^\]]+)?` in the fallback pattern construction to ensure it terminates on any alphanumeric or invalid ID.
- **Test:** An artifact block terminated by `[COM some-id]` or `[COM invalid!id]` at BOL correctly terminates.

### Task 6: Add ID validation helper

- **Objective:** Provide a shared validation function for use by all three splitting passes.
- **Implementation:** Add `_validate_block_id(id_str: str) -> bool` that checks the ID matches `^[a-zA-Z0-9_.\-]+$`. Each splitting pass calls this after capturing the ID text; if invalid, produces an `ErrorBlock`.
- **Test:** Valid IDs (`com-1`, `note.2`, `my_block`) pass; invalid IDs (`invalid!id`, `has space`, `@bad`) fail.

### Task 7: Add deterministic short hash generation for blocks without explicit IDs

- **Objective:** When no ID is provided, generate a stable short hash from `sha256(marker + content + filepath)`.
- **Implementation:** Add a helper `generate_block_id(marker: str, content: str, filepath: str) -> str` returning the first 8 hex chars of the SHA-256 digest. Call from all three splitting passes when ID is None.
- **Test:** Same content/marker/filepath always produces the same ID; different inputs produce different IDs.

### Task 8: Add global uniqueness validation in `build_block_tree()`

- **Objective:** After all blocks are collected, check that no two TextBlocks with user-provided (explicit) IDs share the same ID for a given marker type.
- **Implementation:** Modify `build_block_tree()` to return `(BlockTree, list[str])` (tree + errors). Iterate all TextBlocks, group by `(marker, id)` where the ID was explicitly specified by the user, report duplicates. Update callers in `cli.py`.
- **Test:** Two files with user-specified `[COM com-1]` produce a duplicate ID error; two files with `[COM]` (no ID, auto-generated hash) do NOT conflict even if their contents are identical.

### Task 9: Thread file path context through the marker splitting pipeline

- **Objective:** The splitting methods need the file path to generate deterministic IDs.
- **Implementation:** Add `filepath` parameter to `_split_text_block_by_markers()` and propagate to sub-methods.
- **Test:** Covered by Task 7 tests (deterministic ID depends on filepath).

### Task 10: Update documentation

- **Objective:** Update `docs/reference/obsidian.md` fragment markers section.
- **Implementation:** Replace "numbered variants" documentation with new ID syntax. Document validation rules and auto-generation behavior.
