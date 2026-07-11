# Marker Renumber Command

## Problem Statement

Non-artifact marked text blocks (e.g., `[COM]content[/COM]`, `[NOTE]content`) don't always have explicit IDs. The system assigns deterministic hash-based IDs at publish time, but users want a CLI command to permanently assign sequential numeric IDs to all unmarked blocks in source files, making them stable anchors for cross-referencing and publishing.

## Requirements

1. New CLI command: `edit renumber-markers` under the flat `edit` group
2. Scans input records that have configured fragment markers
3. For each marker type independently: finds the maximum existing numeric ID, then assigns `max + 1`, `max + 2`, etc. to blocks without explicit IDs. If no existing numeric IDs for a marker type, starts from 1.
4. IDs are plain integers written as `[MARKER N]` in the opening tag (space between marker name and number)
5. Preserves the original marker format (closed, unclosed, line-prefix) and the original casing of the marker name
6. Supports `--all` (renumber across all records) or `--section <name>` (restrict to a specific input record)
7. Supports `--dry-run` flag
8. Only the obsidian driver is supported (same constraint as markers themselves)
9. Files are written with Unix-style line endings (LF)

## Background

- Marked blocks are extracted via `_split_text_block_by_markers()` in `MarkdownExtractor`, which produces `TextBlock(content, marker, id, explicit_id)`.
- The regex patterns capture an optional ID: `\[(MARKER)(?:\s+([^\]]+))?\]`
- Existing `explicit_id=True` marks blocks with user-given IDs; `explicit_id=False` blocks have hash-based IDs assigned at publish time.
- The extraction pipeline skips code blocks, HTML comments, and main artifact blocks when splitting by fragment markers. A naive file-level regex would incorrectly match literal marker tags inside those regions.
- The approach mirrors `edit_attrs.py`: extract blocks per file → compute changes → atomic writes.

## ID Format

- Plain integer: `1`, `2`, `3`, ...
- Written in the opening marker tag: `[COM 1]`, `[NOTE 3]`
- Numbering is independent per marker type (COM numbering does not affect NOTE numbering)
- Non-sequential (gaps allowed from existing IDs; new IDs continue from max)
- Existing numeric IDs are parsed via `int()` and must be non-negative (≥ 0). Leading zeros are accepted during parsing (e.g., `[COM 005]` is treated as ID `5`) but new IDs are written without leading zeros.

## Case Preservation

The original casing of the marker tag name in the source file is preserved when adding an ID:

| Source | Result |
|--------|--------|
| `[COM]content[/COM]` | `[COM 3]content[/COM]` |
| `[com]content[/com]` | `[com 3]content[/com]` |
| `[Com]content[/Com]` | `[Com 3]content[/Com]` |

The closing tag is never modified.

## Marker Format Preservation

Each marker format is preserved after renumbering:

| Format | Before | After |
|--------|--------|-------|
| Closed paired | `[COM]content[/COM]` | `[COM 3]content[/COM]` |
| Unclosed paired | `[COM]content` (terminated by empty line/heading/EOF) | `[COM 3]content` |
| Line-prefix | `[COM] content` | `[COM 3] content` |

The closing tag `[/MARKER]` is never modified.

## CLI Interface

```
syntagmax edit renumber-markers [CONFIG_PATH] [OPTIONS]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `[CONFIG_PATH]` | No | `.syntagmax/config.toml` | Path to config file (positional argument) |
| `--all` | No* | — | Renumber all unmarked blocks across all input records |
| `--section <name>` | No* | — | Only renumber blocks in a specific input record |
| `--marker <name>` | No | — | Filter: only renumber blocks of a specific marker type |
| `--dry-run` | No | — | Show planned changes without modifying files |

*Either `--all` or `--section` is required.

### Examples

```bash
# Renumber all unmarked blocks across the project
syntagmax edit renumber-markers --all

# Dry-run to preview changes
syntagmax edit renumber-markers --all --dry-run

# Only renumber COM markers in a specific section
syntagmax edit renumber-markers --section system-requirements --marker COM

# Using a custom config path
syntagmax edit renumber-markers .syntagmax/config.toml --all
```

## Algorithm

1. Load configuration; select input records based on `--all` or `--section`.
2. Filter to records that have `markers` configured and use the obsidian driver.
3. For each record, use the extractor to extract blocks from each file, collecting exact character offsets of each opening tag.
4. Collect all TextBlocks with `explicit_id=True` where `id` parses as a non-negative integer via `int()` — these are existing numbered markers.
5. Per marker type, compute `max_id = max(existing_numeric_ids)` or `0` if none exist.
6. Per marker type, set `next_id = max_id + 1`.
7. For each TextBlock with `marker` set but `explicit_id=False` (no user-given ID):
   - Assign `next_id` for that marker type
   - Increment `next_id`
8. Determine the exact character offsets (start, end) of each unmarked opening tag from the extraction pass. This ensures only actual parsed blocks are modified — literal marker tags inside code blocks, HTML comments, or artifact blocks are never touched.
9. Apply changes by performing string replacements at these offsets, sorted in reverse (bottom-to-top) order to prevent offset drift. Preserve the matched marker casing (e.g., `com` stays as `com`).
10. Atomic writes: compute all changes in memory before writing files with Unix-style line endings (LF).

## Ordering

Blocks are processed in file order (sorted filepaths within each input record, then block order within each file). This ensures deterministic, stable ID assignment.

## Output

### Dry-run mode

For each planned change, log to console:
```
DRY-RUN: Would assign [COM 3] in docs/SYS/SYS-001.md
```

Print summary:
```
Summary: N blocks would be renumbered, M already have IDs
```

### Normal mode

For each applied change, log to console:
```
Assigned [COM 3] in docs/SYS/SYS-001.md
```

Print summary:
```
Summary: N blocks renumbered across M files
```

## Edge Cases

- Blocks that already have explicit IDs (numeric or non-numeric) are never modified.
- Non-numeric explicit IDs (e.g., `[COM intro]`) do not contribute to `max_id` computation.
- Existing IDs with leading zeros (e.g., `[COM 005]`) are parsed as `int("005") = 5` and contribute to `max_id`.
- Negative integers in IDs are treated as non-numeric (invalid) and do not contribute to `max_id`.
- If `--marker` is specified but no input record configures that marker, warn and exit.
- If `--section` is specified but the section does not exist or has no markers configured, error and exit.
- If no blocks need renumbering, print a summary and exit cleanly.
- Multiple input records may configure the same marker type — numbering is shared across records for the same marker type (global max across all targeted records).
- Literal marker tags inside code blocks, HTML comments, or main artifact blocks are never modified (guaranteed by offset-based replacement from the extraction pass).

## Implementation Notes

- New module: `src/syntagmax/edit_markers.py`
- CLI wiring: add `renumber-markers` command under `edit` group in `cli.py`
- File modification strategy: during extraction, record character offsets of each opening marker tag. In the write phase, replace at exact offsets (bottom-to-top to avoid drift). Write with `newline=''` and ensure LF endings.
- The extraction pass must be extended to return offset information for TextBlocks. This can be done by modifying `_split_text_block_by_markers()` to record match positions relative to the file content, or by running a secondary targeted pass on the raw file content using the same regex patterns but only at positions corresponding to extracted unmarked blocks.
- The offset information ties a TextBlock to its exact opening tag position in the source file, enabling safe surgical replacement.

## Task Breakdown

### Task 1: Offset Tracking in Block Extraction

Extend the marker splitting pipeline to record the character offset of each TextBlock's opening tag within the source file. This can be achieved by:
- Adding an `offset` or `source_span` field to `TextBlock` (or a parallel data structure)
- Propagating match positions from `_split_text_block_by_markers()` through to the caller

**Test:** Unit test verifying that extracted TextBlocks carry correct character offsets that point to their opening `[MARKER]` tag in the source content.

### Task 2: Core Logic (`src/syntagmax/edit_markers.py`)

Create the module with `renumber_markers(config: Config, section: str | None, marker_filter: str | None, dry_run: bool)`:
- Select target records (all with markers, or specific section)
- Extract blocks per file with offset tracking
- Scan for existing numeric IDs per marker type (non-negative integers via `int()`)
- Assign new sequential IDs to blocks without explicit IDs
- Perform offset-based bottom-to-top file rewrites preserving marker casing
- Atomic writes with LF line endings
- Log each assignment to console; print summary

**Test:** Unit test with a temp project containing multiple markers (COM, NOTE), some with existing numeric IDs and some without. Verify correct sequential IDs assigned per marker type starting from max+1. Verify code blocks with literal markers are not touched.

### Task 3: CLI Wiring

Add `renumber-markers` command under `edit` in `cli.py`:
- Accepts `[CONFIG_PATH]` positional argument (default `.syntagmax/config.toml`)
- Accepts `--all` or `--section <name>` (one required)
- Accepts `--marker <name>` (optional filter)
- Accepts `--dry-run`
- Validates mutual exclusivity / requirement of `--all` vs `--section`
- Calls `renumber_markers()`

**Test:** Integration test via Click's test runner on a temp project.

### Task 4: End-to-End Test

Create a test fixture with:
- Closed markers with and without IDs (various casings)
- Unclosed markers with and without IDs
- Line-prefix markers with and without IDs
- Multiple marker types (COM, NOTE)
- Existing non-sequential numeric IDs (e.g., 2, 5) and IDs with leading zeros
- Literal marker tags inside code blocks (must not be modified)
- Content inside main artifact blocks referencing markers (must not be modified)

Verify:
- Existing IDs preserved unchanged
- New IDs start from max+1 per marker type
- All three formats handled correctly
- Original marker casing preserved
- Code block content untouched
- Re-extraction confirms `explicit_id=True` for all previously unnumbered blocks
- Written files use LF line endings

### Task 5: README Documentation

Add subsection under "Editing and Renumbering" describing `edit renumber-markers`, its options, and example usage.
