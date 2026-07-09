# Spec: Simple Requirement or Text Block Terminator (Empty Line)

## Problem Statement

Currently, artifact blocks (`[REQ]...[/REQ]`) and marked text blocks (`[COM]...[/COM]`) in the Obsidian driver can only be terminated by an explicit `[/TAG]` closing syntax or a YAML block. Users want blocks to also terminate at one or more empty lines, making authoring in Obsidian more natural.

## Requirements

1. Both termination methods coexist: `[/TAG]` still works, empty line(s) are an additional terminator
2. Empty line terminates unconditionally — if a YAML block is needed, no empty lines are allowed between the opening marker and the YAML
3. This applies to both artifact blocks and paired marked text blocks
4. A single empty line (i.e., `\n\n` or `\n\r\n`) is sufficient to terminate
5. The terminating empty line(s) are consumed (not included in subsequent text)

## Background

- The Obsidian extractor inherits from `MarkdownExtractor`
- Segment boundaries are determined in `_extract_blocks_from_markdown()` *before* the Lark parser is invoked
- The Lark grammar (`markdown.lark`) defines `terminator: yaml_block | _REQ_END` — both require explicit syntax
- The `_split_text_block_by_markers()` method handles marked text blocks (paired mode: `[COM]...[/COM]`; line-prefix mode already terminates on `\n\n`)
- Existing examples in the repo have no blank lines inside artifact blocks
- `_update_yaml_attrs` and `_insert_inline_field` already have fallbacks for when `[/MARKER]` is absent

## Proposed Solution

1. **Segment detection level** (`_extract_blocks_from_markdown`): When looking for segment end, also search for an empty line (`\n\n` or `\r\n\r\n`) as a boundary. The priority is: YAML block > `[/TAG]` > empty line. If an empty line is found before `[/TAG]` or YAML, use it as the segment end.
2. **Lark grammar**: Make the `terminator` rule optional so the parser can handle segments that end without `[/TAG]` or YAML.
3. **Marked text blocks** (`_split_text_block_by_markers`): In the paired-mode regex, also allow empty line as terminator (match `[MARKER]...\n\n` in addition to `[MARKER]...[/MARKER]`).

## Task Breakdown

### Task 1: Update Lark grammar to make terminator optional

- **Objective:** Allow the parser to successfully parse an artifact block that has no explicit `[/TAG]` closing tag and no YAML block.
- **Implementation:** Change the grammar rule `req: _REQ_BEGIN _NL? [contents] (field | _NL)* terminator` to make `terminator` optional: `req: _REQ_BEGIN _NL? [contents] (field | _NL)* [terminator]`
- Update `MarkdownTransformer.req()` to handle the case where `terminator` is missing (no last element of type dict with 'type' key).
- **Test:** Write a unit test that parses `[REQ]\nSome content\n[id] REQ-001\n` (no terminator) — parser should succeed and return the artifact with id REQ-001.
- **Demo:** `uv run pytest tests/test_empty_line_terminator.py::test_grammar_no_terminator` passes.

### Task 2: Update segment boundary detection for empty-line termination of artifact blocks

- **Objective:** In `_extract_blocks_from_markdown()`, detect empty lines as block boundaries when no YAML or `[/TAG]` is found before them.
- **Implementation:**
  - After finding `start_pos` of a `[MARKER]`, search for the first empty line (regex `\n\s*\n` or `\r\n\s*\r\n`) in the text after the marker.
  - Boundary priority: (1) YAML block if found before the empty line, (2) `[/TAG]` if found before the empty line, (3) the empty line position itself.
  - When empty line terminates, `segment_end` is set to the position of the first `\n` in the empty line sequence (content before it). The empty line(s) themselves are consumed (advance `pos` past them).
  - Existing `segment_end == -1` error ("Unterminated requirement") becomes a fallback only when none of the three terminators is found (e.g., end of file without empty line).
- **Test:** Write tests with:
  - `[REQ]\ncontent\n[id] REQ-001\n\nMore text` → artifact + text block
  - `[REQ]\ncontent\n[id] REQ-001\n[/REQ]\nMore text` → still works (backward compat)
  - `[REQ]\ncontent\n[id] REQ-001\n```yaml\nattrs:\n  x: 1\n```\n\nMore text` → YAML takes priority
- **Demo:** `uv run pytest tests/test_empty_line_terminator.py::TestArtifactBlocks` passes.

### Task 3: Update paired marked text block splitting for empty-line termination

- **Objective:** Modify `_split_text_block_by_markers()` so the paired-mode regex also matches blocks terminated by a double newline.
- **Implementation:**
  - Change the paired regex from `\[({escaped})\](.*?)\[/\1\]` to also match `\[({escaped})\](.*?)(?:\[/\1\]|\n\s*\n)` (non-greedy, first match wins).
  - When terminated by empty line, the empty line is consumed (not part of the matched content or subsequent text).
  - If `[/TAG]` appears before the empty line, it still wins (non-greedy `.*?` ensures shortest match).
- **Test:** Write tests with:
  - `[COM]comment text\n\nafter` → `TextBlock(content='comment text', marker='COM')` + `TextBlock(content='after', marker=None)`
  - `[COM]comment text[/COM] after` → still works (backward compat)
  - `[COM]line1\nline2\n\nafter` → multiline content terminated by empty line
- **Demo:** `uv run pytest tests/test_empty_line_terminator.py::TestMarkedTextBlocks` passes.

### Task 4: Handle edge cases and integration tests

- **Objective:** Cover edge cases for the new termination mode and ensure no regressions.
- **Implementation:** Add tests for:
  - End-of-file without empty line and without `[/TAG]` → should still produce an artifact (end of string as implicit terminator)
  - Multiple consecutive empty lines → single termination, extra empty lines are consumed
  - `\r\n\r\n` (Windows line endings) → works as terminator
  - Artifact followed immediately by another artifact with no gap: `[REQ]...\n\n[REQ]...`
  - Marked text block followed by artifact: `[COM]text\n\n[REQ]...`
  - Existing test suite passes: `uv run pytest` (full)
- **Test:** All new and existing tests pass.
- **Demo:** `uv run pytest` all green.

### Task 5: Update example files and documentation

- **Objective:** Add an example demonstrating empty-line termination and update relevant docs.
- **Implementation:**
  - Add a new example requirement file (e.g., `example/obsidian-driver/REQ/REQ-006.md`) that uses empty-line termination instead of `[/REQ]`.
  - Update the seed document `docs/seed/simple-req-or-block-term.md` into a spec document.
  - Update `README.md` to mention that blocks can also be terminated by empty lines.
- **Test:** `uv run syntagmax --cwd ./example/obsidian-driver/ analyze` runs without errors and picks up REQ-006.
- **Demo:** Analysis includes the new artifact; documentation reflects the feature.
