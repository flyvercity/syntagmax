# Spec: Simple Requirement or Text Block Terminator (Empty Line)

## Problem Statement

Currently, artifact blocks (`[REQ]...[/REQ]`) and marked text blocks (`[COM]...[/COM]`) in the Obsidian driver can only be terminated by an explicit `[/TAG]` closing syntax or a YAML block. Users want blocks to also terminate at one or more empty lines, making authoring in Obsidian more natural.

## Requirements

1. Both termination methods coexist: `[/TAG]` still works, empty line(s) are an additional terminator
2. Empty line terminates contextually: it only acts as a terminator if no explicit `[/TAG]` closing tag or ````yaml` block is present in the block.
3. This applies to both artifact blocks and paired marked text blocks
4. A single empty line (i.e., `\n\n` or `\n\r\n`) is sufficient to terminate
5. The terminating empty line(s) are consumed (not included in subsequent text)
6. A `[MARKER]` matching one of the configured fragment markers (e.g., `[COM]`, `[NOTE]`) terminates the current artifact block (context-aware, same as empty line — only when no explicit `[/TAG]` or YAML block is present)
7. A line starting with `#` (Markdown heading or Obsidian tag) terminates the current artifact block (context-aware, same as empty line — only when no explicit `[/TAG]` or YAML block is present)
8. Fragment marker names must not overlap with attribute names defined in the metamodel for the same artifact type — collision is a fatal config/validation error
9. Complete list of artifact block terminators (in priority order):
   1. YAML block (````yaml...`````)
   2. Explicit closing tag (`[/TAG]`)
   3. Another artifact start marker (`[MARKER]` for the same input record's artifact type)
   4. A configured fragment marker (`[COM]`, `[NOTE]`, etc.)
   5. A line starting with `#`
   6. One or more empty lines
   7. End of file

## Background

- The Obsidian extractor inherits from `MarkdownExtractor`
- Segment boundaries are determined in `_extract_blocks_from_markdown()` *before* the Lark parser is invoked
- The Lark grammar (`markdown.lark`) defines `terminator: yaml_block | _REQ_END` — both require explicit syntax
- The `_split_text_block_by_markers()` method handles marked text blocks (paired mode: `[COM]...[/COM]`; line-prefix mode already terminates on `\n\n`)
- Existing examples in the repo have no blank lines inside artifact blocks
- `_update_yaml_attrs` and `_insert_inline_field` already have fallbacks for when `[/MARKER]` is absent

## Proposed Solution

1. **Segment detection level** (`_extract_blocks_from_markdown`): Keep existing detection of ````yaml` and `[/TAG]`. If neither is found before the next requirement start marker, search for the earliest of: (a) a configured fragment marker at BOL, (b) a line starting with `#`, (c) the first empty line (`\n\s*\n` or `\r\n\s*\r\n`), (d) end of file. Use whichever comes first as the segment boundary. Set `segment_end` to the position immediately *after* the last content line's `\n` (to include the trailing newline for the parser). Consume any remaining newlines/whitespace when advancing `pos`.
2. **Lark grammar & Transformer**: Make the `terminator` rule optional: `req: _REQ_BEGIN _NL? [contents] (field | _NL)* [terminator]`. Update `MarkdownTransformer.req(self, t)` to check if `t[-1]` represents a terminator (a dictionary with a `'type'` key). If not, treat `t[-1]` as a normal field/content child and do not exclude it.
3. **Marked text blocks** (`_split_text_block_by_markers`): Split paired markers in two passes: first extract fully closed paired blocks `\[({escaped})\](.*?)\[/\1\]`, then extract unclosed paired blocks using `\[({escaped})\](.*?)(?=\n\s*\n|\Z)`.
4. **Config validation**: Validate that configured fragment markers do not collide with metamodel attribute names for the relevant artifact type — raise `FatalError` on collision.

## Task Breakdown

### Task 1: Update Lark grammar and transformer to make terminator optional

- **Objective:** Allow the parser to successfully parse an artifact block that has no explicit `[/TAG]` closing tag and no YAML block.
- **Implementation:** Change the grammar rule `req: _REQ_BEGIN _NL? [contents] (field | _NL)* terminator` to make `terminator` optional: `req: _REQ_BEGIN _NL? [contents] (field | _NL)* [terminator]`
- Update `MarkdownTransformer.req(self, t)` to check if `t[-1]` is a valid terminator (a dict with a `'type'` key representing `'yaml'` or `'slash_req'`). If it is not a terminator, treat `t[-1]` as a normal field/content child and do not exclude it from the fields/contents loop.
- **Test:** Write a unit test that parses `[REQ]\nSome content\n[id] REQ-001\n` (no terminator) — parser should succeed and return the artifact with id REQ-001.
- **Demo:** `uv run pytest tests/test_empty_line_terminator.py::test_grammar_no_terminator` passes.

### Task 2: Update segment boundary detection for empty-line termination of artifact blocks

- **Objective:** In `_extract_blocks_from_markdown()`, detect additional block boundaries (fragment markers, `#` lines, empty lines) only when no YAML or `[/TAG]` is found before them (context-aware fallback).
- **Implementation:**
  - Keep existing detection of ````yaml` and `[/TAG]` unchanged — these remain the highest-priority terminators.
  - If neither is found before the next `[MARKER]` start, search for the earliest of:
    1. A configured fragment marker (`[COM]`, `[NOTE]`, etc.) appearing at the beginning of a line.
    2. A line starting with `#` (heading or tag).
    3. The first empty line (`\n\s*\n` or `\r\n\s*\r\n`).
    4. End of file.
  - Use whichever comes first as the segment boundary.
  - When any of these terminates, set `segment_end` to the position immediately *after* the last content line's `\n` (to include the trailing newline the Lark parser requires). Consume remaining consecutive whitespace/newlines when advancing `pos`.
  - Fragment markers and `#` lines are NOT consumed — they remain available for subsequent parsing (as text blocks or the next extraction pass).
  - Existing `segment_end == -1` error ("Unterminated requirement") becomes a fallback only when none of the terminators is found (should not happen given end-of-file fallback).
- **Test:** Write tests with:
  - `[REQ]\ncontent\n[id] REQ-001\n\nMore text` → artifact + text block (empty line terminates)
  - `[REQ]\ncontent\n[id] REQ-001\n[/REQ]\nMore text` → still works (backward compat)
  - `[REQ]\ncontent\n[id] REQ-001\n\n```yaml\nattrs:\n  x: 1\n```\n` → YAML takes priority when present
  - Multi-paragraph requirement with `[/REQ]`: `[REQ]\npara 1\n\npara 2\n[id] REQ-001\n[/REQ]` → works correctly, empty line inside does NOT terminate because `[/REQ]` is present
  - `[REQ]\ncontent\n[id] REQ-001\n[COM]comment text[/COM]` → fragment marker terminates the artifact
  - `[REQ]\ncontent\n[id] REQ-001\n# Next Section` → heading terminates the artifact
  - End of file without any terminator → artifact is still extracted
- **Demo:** `uv run pytest tests/test_empty_line_terminator.py::TestArtifactBlocks` passes.

### Task 3: Update paired marked text block splitting for empty-line termination

- **Objective:** Modify `_split_text_block_by_markers()` so paired-mode also supports empty-line termination without breaking multi-paragraph closed blocks.
- **Implementation:**
  - Use a two-pass approach:
    1. First pass: extract fully closed paired blocks using existing regex `\[({escaped})\](.*?)\[/\1\]` (unchanged behavior).
    2. Second pass: on remaining text, extract unclosed paired blocks that start with `[MARKER]` and terminate at the first double-newline boundary or end-of-string, using `\[({escaped})\](.*?)(?=\n\s*\n|\Z)`.
  - When terminated by empty line, the empty line is consumed (not part of the matched content or subsequent text).
  - If `[/TAG]` is present, the first pass captures it and the second pass never sees it.
- **Test:** Write tests with:
  - `[COM]comment text\n\nafter` → `TextBlock(content='comment text', marker='COM')` + `TextBlock(content='after', marker=None)`
  - `[COM]comment text[/COM] after` → still works (backward compat)
  - `[COM]line1\nline2\n\nafter` → multiline content terminated by empty line
  - `[COM]para1\n\npara2[/COM]` → multi-paragraph comment with explicit close tag works correctly
- **Demo:** `uv run pytest tests/test_empty_line_terminator.py::TestMarkedTextBlocks` passes.

### Task 4: Validate fragment markers do not collide with metamodel attributes

- **Objective:** Ensure configured fragment markers cannot overlap with attribute names in the metamodel.
- **Implementation:**
  - During config validation (or at extraction time when metamodel is available), check that none of the configured `markers` match any attribute name defined in the metamodel for the relevant artifact type.
  - Comparison should be case-insensitive.
  - Raise `FatalError` on collision with a clear message indicating which marker conflicts with which attribute.
- **Test:** Write a unit test with a marker name that matches a metamodel attribute (e.g., `markers = ["status"]` when metamodel defines `attribute status`) → raises `FatalError`.
- **Demo:** `uv run pytest tests/test_empty_line_terminator.py::TestMarkerAttributeCollision` passes.

### Task 5: Handle edge cases and integration tests

- **Objective:** Cover edge cases for the new termination mode and ensure no regressions.
- **Implementation:** Add tests for:
  - End-of-file without empty line and without `[/TAG]` → should still produce an artifact (end of string as implicit terminator)
  - Multiple consecutive empty lines → single termination, all consecutive whitespace/newlines are consumed
  - `\r\n\r\n` (Windows line endings) → works as terminator
  - Artifact followed immediately by another artifact with no gap: `[REQ]...\n\n[REQ]...`
  - Marked text block followed by artifact: `[COM]text\n\n[REQ]...`
  - Multi-paragraph requirement with explicit `[/REQ]` → empty lines inside do NOT terminate (backward compat)
  - Blank line before ````yaml` block with `[/TAG]` present → does NOT terminate (YAML/tag take priority)
  - Fragment marker at BOL terminates artifact (context-aware)
  - `#` at BOL terminates artifact (context-aware)
  - `#` inside a line (not at BOL) does NOT terminate
  - Fragment marker inside content (not at BOL) does NOT terminate
  - Existing test suite passes: `uv run pytest` (full)
- **Test:** All new and existing tests pass.
- **Demo:** `uv run pytest` all green.

### Task 6: Update example files and documentation

- **Objective:** Add an example demonstrating empty-line termination, create dedicated documentation for termination rules, and update relevant docs.
- **Implementation:**
  - Create a new documentation file `docs/reference/block-termination.md` with a clear, detailed description of all termination rules for the Obsidian driver. This file should include:
    - An overview explaining what block termination means and why multiple strategies exist
    - The complete priority-ordered list of terminators with explanations and examples for each:
      1. YAML block — example showing ````yaml` as terminator
      2. Explicit closing tag (`[/TAG]`) — example with `[/REQ]`, `[/COM]`
      3. Another artifact start marker — example showing back-to-back artifacts
      4. A configured fragment marker at BOL — example with `[COM]` terminating a `[REQ]`
      5. A line starting with `#` — example with heading terminating a block
      6. One or more empty lines — example with blank line terminating
      7. End of file — implicit termination
    - A section on context-aware vs. unconditional behavior: explain that terminators 4–7 only apply when no YAML block or `[/TAG]` is present, and that when `[/TAG]` or YAML exists, empty lines and headings inside blocks are allowed
    - A section on fragment marker / attribute name collision validation
    - A "Migration Guide" subsection for users transitioning from always using `[/TAG]`
  - Add a new example requirement file (e.g., `example/obsidian-driver/REQ/REQ-006.md`) that uses empty-line termination instead of `[/REQ]`
  - Update `README.md` to mention that blocks can also be terminated by empty lines, with a link to `docs/reference/block-termination.md` for full details
  - Link the new doc from the existing configuration reference (`docs/reference/configuration.md`) under the Obsidian driver section
- **Test:** `uv run syntagmax --cwd ./example/obsidian-driver/ analyze` runs without errors and picks up REQ-006.
- **Demo:** Analysis includes the new artifact; documentation is comprehensive and cross-linked.
