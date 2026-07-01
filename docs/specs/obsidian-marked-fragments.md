# Spec: Obsidian Marked Fragments

## Problem Statement

Add support for non-artifact marked fragments (e.g. `[COM]...[/COM]`, `[NOTE]...[/NOTE]`) in Obsidian files, configured per input record. These fragments are extracted as `TextBlock`s with a `marker` field, to be used later for publication filtering.

## Requirements

- Markers are configured via a `markers` list on the input record (config level)
- Markers are case-insensitive
- No nesting or overlap between fragment markers
- Fragment markers must not collide with the artifact marker — collision is a fatal config error
- `TextBlock` gains a `marker: str | None` field (`None` = regular unmarked text)
- Obsidian driver only in this version

## Example

Config:

```toml
[[input]]
name = "system-requirements"
dir = "SYS"
driver = "obsidian"
markers = ["COM", "NOTE"]
```

Input text:

```text
This is a sample preamble text. [COM]This is a special comment text [/COM].
[note]This a a special note text[/note]
Some more text
[SYS]This is a text for the requirement[ID]SYS-000[/SYS]
```

Extracted blocks:
- `TextBlock(content='This is a sample preamble text. ', marker=None)`
- `TextBlock(content='This is a special comment text ', marker='COM')`
- `TextBlock(content='.\n', marker=None)`
- `TextBlock(content='This a a special note text', marker='NOTE')`
- `TextBlock(content='\nSome more text\n', marker=None)`
- `ArtifactBlock(artifact=..., raw_text='[SYS]...[/SYS]')`

## Background

- `ObsidianExtractor` inherits from `MarkdownExtractor`
- `MarkdownExtractor._extract_blocks_from_markdown()` currently scans for a single artifact marker (`[MARKER]...[/MARKER]` or `[MARKER]...```yaml...```)
- Text between artifacts becomes `TextBlock(content=...)` with no marker
- `InputRecord` is a dataclass; `InputConfig` is the pydantic model for TOML parsing
- Config validation happens in `Config._read_input_records()`

## Proposed Solution

1. Add `markers: list[str]` to `InputConfig` and `InputRecord`
2. Validate no collision between `markers` and the artifact `marker` at config load time
3. Extend `TextBlock` with `marker: str | None = None`
4. In `MarkdownExtractor._extract_blocks_from_markdown()`, after extracting artifact blocks and collecting inter-artifact text, split that text further by fragment markers into marked/unmarked `TextBlock`s
5. Amend example and README

## Task Breakdown

### Task 1: Extend `TextBlock` data model

- **Objective:** Add an optional `marker` field to `TextBlock`
- **Implementation:** Add `marker: str | None = None` to the `TextBlock` dataclass in `blocks.py`
- **Test:** Existing tests remain green (default `None` is backward-compatible). Add a unit test confirming `TextBlock(content='x', marker='COM')` works.
- **Demo:** `uv run pytest tests/test_publish.py` passes without changes; new marker field is accessible.

### Task 2: Add `markers` to config model and `InputRecord`, with collision validation

- **Objective:** Allow `markers = ["COM", "NOTE"]` in TOML input config; validate no collision with artifact marker.
- **Implementation:**
  - Add `markers: list[str] = Field(default_factory=list)` to `InputConfig`
  - Add `markers: list[str]` to `InputRecord` dataclass
  - In `Config._read_input_records()`, pass markers through and validate: if any marker (case-insensitive) equals the artifact marker, raise `FatalError`
- **Test:** Unit test that a config with colliding markers raises `FatalError`; config with valid markers loads successfully.
- **Demo:** Loading a config with `markers = ["COM"]` and `marker = "REQ"` succeeds; loading with `markers = ["REQ"]` and `marker = "REQ"` fails fatally.

### Task 3: Implement fragment splitting in `MarkdownExtractor`

- **Objective:** After artifact extraction, split inter-artifact text by configured fragment markers into marked and unmarked `TextBlock`s.
- **Implementation:**
  - In `_extract_blocks_from_markdown()`, after the main loop produces the `blocks` list, add a post-processing step:
    - For each `TextBlock` in the list, scan its `content` for `[MARKER]...[/MARKER]` patterns (case-insensitive) using the configured `self._record.markers`
    - Split into a sequence of `TextBlock(content=..., marker=None)` and `TextBlock(content=..., marker='COM')` etc.
    - Replace the original `TextBlock` with the split sequence
  - This keeps the artifact extraction logic untouched and cleanly separates concerns.
- **Test:** Unit test with markdown containing `[COM]comment[/COM]` between artifacts; verify the block list contains marked `TextBlock`s with correct marker values and content.
- **Demo:** Extracting from a file with `[COM]...[/COM]` produces `TextBlock(content='comment', marker='COM')` in the block list.

### Task 4: Add comprehensive tests for edge cases

- **Objective:** Cover edge cases for marked fragments.
- **Implementation:** Test file `tests/test_marked_fragments.py` with cases:
  - Multiple different markers in one file
  - Marker at start/end of file
  - Adjacent markers with no gap
  - Case-insensitivity (`[com]...[/COM]`, `[Com]...[/com]`)
  - Empty marker content `[COM][/COM]`
  - Unmarked text between marked fragments has `marker=None`
  - Fragment markers don't interfere with artifact parsing
- **Test:** All pass.
- **Demo:** `uv run pytest tests/test_marked_fragments.py` all green.

### Task 5: Amend the obsidian example to showcase the capability

- **Objective:** Update the example project to demonstrate marked fragments.
- **Implementation:**
  - Add `markers = ["COM", "NOTE"]` to the `system-requirements` input in `example/obsidian-driver/.syntagmax/config.toml`
  - Add `[COM]...[/COM]` and `[NOTE]...[/NOTE]` fragments to one of the existing `.md` files (e.g., `SYS/SYS-001.md`)
- **Test:** Run `uv run syntagmax --cwd ./example/obsidian-driver/ analyze` — no errors.
- **Demo:** Analysis runs cleanly; publish output shows the marked fragments as text blocks.

### Task 6: Update README.md documentation

- **Objective:** Document the new `markers` config option and its behavior.
- **Implementation:**
  - Add `markers` to the Input sources table in README
  - Add a section explaining marked fragments with the example from the seed doc
  - Note case-insensitivity and collision validation
- **Test:** N/A (documentation)
- **Demo:** README accurately describes the feature with example.

## Follow-up Tasks

- Amend the obsidian example to showcase the capability (Task 5)
- Amend README.md (Task 6)
