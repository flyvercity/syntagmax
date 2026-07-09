# Specification: Numeric Prefix Stripping for Directory/File Headings in Publish

## Problem Statement

The `remove_numeric_prefixes_in_headers` parameter currently only strips numeric prefixes from Markdown heading lines within text content. It should also strip them from directory and filenames when they become headings in the published output. Additionally, `render_block_tree` needs to decompose `FileRecord.path` into nested directory/file headings, and the record name heading should only appear when multiple records are published together.

## Requirements

1. Each unique directory component in a file's relative path (excluding the record's `dir` prefix) becomes a heading at a progressively deeper level.
2. The file stem (without extension) becomes the deepest heading before its blocks.
3. `remove_numeric_prefixes_in_headers` applies to these directory/file headings (stripping `01-`, `2.1 `, etc.).
4. The record name heading is only emitted when multiple records are being published (`--all` or multiple named records). When a single record is published, no record name heading appears.
5. The record name heading is also subject to `remove_numeric_prefixes_in_headers`.
6. Directories containing only one file still emit a heading.
7. File extensions are stripped from the filename heading.
8. Duplicate consecutive directory headings are not re-emitted (i.e., if two files share a directory path, the directory heading appears once).

## Background

- `render_block_tree(tree, config)` iterates over `tree.inputs` → `input_block.files` → `file_record.blocks`
- `FileRecord.path` is relative to `_base_dir` (e.g., `SYS/01-Intro/02-Functional.md`)
- Record's `dir` field gives the top-level directory to strip (e.g., `SYS`)
- `strip_numeric_prefix()` already handles the regex: `^\s*(?:[0-9]+(?:\.[0-9]+)*\s*[-.]?|[0-9]+\s+)(.*)$`
- The CLI filters `tree.inputs` before calling `render_block_tree` for both `--all` and single-record modes
- `InputRecord` has `record_base: Path` (which is `base_dir / dir`)
- `derive_path` produces paths relative to `_base_dir`: `filepath.absolute().relative_to(self._base_dir.absolute()).as_posix()`

### Current Behaviour

- `render_block_tree` always emits the record name as a heading at level `start_level + 1`
- File-level headings are not emitted at all; blocks from each file are rendered sequentially
- `remove_numeric_prefixes_in_headers` only applies within `process_heading_line` to Markdown headings in text blocks

### Example

Given record `dir = "SYS"` and files:
- `FileRecord(path="SYS/01-Intro/02-Functional.md", blocks=[...])`
- `FileRecord(path="SYS/01-Intro/03-Performance.md", blocks=[...])`
- `FileRecord(path="SYS/02-Design/01-Architecture.md", blocks=[...])`

With `start_level=1`, `remove_numeric_prefixes_in_headers=True`, and `--all` (multi-record):

```markdown
# system-requirements

## Intro

### Functional

(blocks...)

### Performance

(blocks...)

## Design

### Architecture

(blocks...)
```

Without `--all` (single record), the `# system-requirements` heading is omitted, and directory headings start at `start_level`:

```markdown
# Intro

## Functional

(blocks...)

## Performance

(blocks...)

# Design

## Architecture

(blocks...)
```

## Proposed Solution

### Architecture

1. Add `multi_record: bool = True` parameter to `render_block_tree`.
2. Accept record directory information from `record_map` to strip the record's `dir` prefix from file paths.
3. Decompose each `FileRecord.path` into path components, emit directory and file headings at appropriate levels.
4. Track previously emitted path components per input block to avoid duplicate directory headings.
5. Apply `strip_numeric_prefix` to record name, directory names, and file stems when `remove_numeric_prefixes_in_headers` is enabled.
6. Wire `multi_record` flag through the CLI based on number of selected records.

### Heading Level Allocation

- Record name heading: `start_level` (only if `multi_record=True`)
- Directory components: `start_level + 1`, `start_level + 2`, ... (offset by 1 if `multi_record=True`, otherwise starting from `start_level`)
- File stem: next level after deepest directory
- All levels capped at 6

### Path Decomposition Logic

```python
from pathlib import PurePosixPath

def decompose_file_path(file_path: str, record_dir: str) -> list[str]:
    """Decompose FileRecord.path into heading components.
    
    Strips the record's dir prefix and file extension.
    Returns list of components: [dir1, dir2, ..., file_stem]
    """
    parts = PurePosixPath(file_path).parts
    dir_parts = PurePosixPath(record_dir).parts
    
    # Strip leading components matching record dir
    if parts[:len(dir_parts)] == dir_parts:
        parts = parts[len(dir_parts):]
    
    # Strip extension from last component (filename)
    if parts:
        parts = list(parts)
        parts[-1] = PurePosixPath(parts[-1]).stem
    
    return list(parts)
```

### Duplicate Directory Tracking

Track `last_components: list[str]` per input block. For each file:
1. Compute new components via `decompose_file_path`.
2. Find the longest common prefix with `last_components`.
3. Only emit headings for components beyond the common prefix.

## Task Breakdown

### Task 1: Add path decomposition and heading emission in `render_block_tree`

**Objective:** Decompose `FileRecord.path` into directory/file headings, track previously emitted components to avoid duplicates, and apply `strip_numeric_prefix` when `remove_numeric_prefixes_in_headers` is enabled.

**Implementation guidance:**
- Add `multi_record: bool = True` parameter to `render_block_tree`.
- From `record_map`, extract each record's `dir` field (available via `InputRecord.record_base` relative to `config._base_dir`, or store the original `dir` string on `InputRecord`).
- For each `input_block`: only emit the record name heading if `multi_record` is True. Apply `strip_numeric_prefix` to the record name if `remove_numeric_prefixes_in_headers` is enabled.
- For each `file_record`: split `path` into components via `decompose_file_path`, track `last_components`, emit only new headings.
- Heading levels: if `multi_record`, record name at `start_level`, path components start at `start_level + 1`. If not `multi_record`, path components start at `start_level`.
- All heading levels capped at 6.

**Test requirements:**
- Test with files in nested directories — verify correct heading structure.
- Test that shared directory prefixes emit the directory heading only once.
- Test `remove_numeric_prefixes_in_headers=True` strips prefixes from dir/file headings.
- Test `remove_numeric_prefixes_in_headers=False` preserves them.
- Test single file in a directory still emits heading.
- Test level capping at 6.

**Demo:** `uv run pytest tests/test_publish.py` passes with new tests.

### Task 2: Wire `multi_record` flag through the CLI

**Objective:** Pass `multi_record=False` when publishing a single record, `multi_record=True` when `--all` or multiple records are selected.

**Implementation guidance:**
- In `cli.py`, in the `--single` branch: pass `multi_record=(len(selected_records) > 1)` to `render_block_tree`.
- In the per-record branch (iterating one record at a time): always pass `multi_record=False`.

**Test requirements:**
- CLI integration test: publish single record → no record name heading in output.
- CLI integration test: publish `--all` with multiple records → record name headings present.

**Demo:** `uv run pytest tests/test_publish.py` passes; manual verification with `uv run syntagmax --cwd ./example/obsidian-driver publish --all`.

### Task 3: Ensure `InputRecord` exposes the original `dir` string

**Objective:** Make the record's configured `dir` value available for path prefix stripping.

**Implementation guidance:**
- Add `dir: str` field to `InputRecord` dataclass (or derive it from `record_base` relative to `_base_dir`).
- Populate it in `Config._read_input_records()` from `input_config.dir`.
- Use it in the path decomposition logic.

**Test requirements:**
- Unit test: `InputRecord.dir` matches the configured `dir` value.

**Demo:** `uv run pytest tests/test_publish.py` passes.

### Task 4: Update existing tests and documentation

**Objective:** Fix any broken assertions from the changed rendering behaviour, update reference documentation.

**Implementation guidance:**
- Update `test_render_basic` — currently asserts `'## reqs' in result`; with `multi_record=True` default this should still pass, but verify heading levels.
- Update `test_publish_cli_basic` — currently asserts `'### rec1' in content`; the single-record publish branch will no longer emit this since `multi_record=False`, so adjust to check for file-level heading or absence of record heading.
- Add a note in `docs/reference/publishing.md` under the `remove_numeric_prefixes_in_headers` parameter explaining it applies to directory/filenames as well.
- Update `docs/reference/configuration.md` if needed.

**Test requirements:**
- All existing tests pass after adjustments.
- `uv run ruff check .` is clean.

**Demo:** `uv run pytest tests` passes; `uv run ruff check .` clean.
