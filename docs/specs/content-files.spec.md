# Specification: Content Files (Headingless File Rendering)

## Problem Statement

The publishing engine uses each file's stem as a heading in the output. Users need a way to designate certain files as "content files" that contribute their content directly at the parent directory's heading level, without generating their own heading. The file participates in normal sort order alongside siblings.

## Requirements

1. Files whose stem exactly matches the configurable marker (default `_contents_`) are treated as content files.
2. Content files are sorted normally with their siblings (alphabetically by path).
3. Content files do NOT emit a filename heading — their blocks render at the directory's own body level (same `content_level` as the directory heading itself, not one level deeper).
4. The marker is configurable via `[drivers.obsidian]` section: `contents_marker = "_contents_"`.
5. The feature only affects the publish pipeline's heading emission, not extraction.

## Background

- `render_block_tree` in `publish.py` iterates files, calls `decompose_file_path` to split path into components, then emits a heading for each new component (including file stem as the last component).
- `content_level` is computed as `path_base_level + len(components)` — one deeper than the file's own heading.
- The `ObsidianDriverConfig` pydantic model in `config.py` already holds driver-level options (`exclude_elements`, `integration`, `root`).
- The config is accessible in `render_block_tree` via `config.obsidian_driver_config`.

## Proposed Solution

### Architecture

1. Add `contents_marker: str` field to `ObsidianDriverConfig` (default `"_contents_"`).
2. In `render_block_tree`, after decomposing path components, check if the last component (file stem) exactly matches the contents marker. If so:
   - Do NOT emit a heading for that file stem (skip the last component from heading emission).
   - Set `content_level` to the directory's heading level (one less than it would normally be), so content renders as the directory's own body.
3. When there's no config passed (no-config mode), use the default marker `"_contents_"`.

### Content Level Calculation

For a normal file with components `[dir1, dir2, filename]`:
- Directory headings at levels: `path_base_level`, `path_base_level + 1`
- File heading at level: `path_base_level + 2`
- Content level: `path_base_level + 3`

For a content file with components `[dir1, dir2, _contents_]`:
- Directory headings at levels: `path_base_level`, `path_base_level + 1`
- No file heading emitted
- Content level: `path_base_level + 2` (same as the deepest directory heading + 1, i.e., the directory's own body)

### Duplicate Heading Tracking

When a file is a content file, `last_components` is updated to include only the directory components (excluding the content file stem). This ensures that subsequent sibling file headings still emit correctly.

### Detection Logic

```python
DEFAULT_CONTENTS_MARKER = '_contents_'

# In render_block_tree:
contents_marker = DEFAULT_CONTENTS_MARKER
if config:
    contents_marker = config.obsidian_driver_config.contents_marker

# After decompose_file_path:
is_content_file = bool(components) and components[-1] == contents_marker
```

The match is exact (case-sensitive) against the file stem. A file named `_contents_intro.md` does NOT match.

## Task Breakdown

### Task 1: Add `contents_marker` option to `ObsidianDriverConfig`

**Objective:** Add the configurable marker string to the driver config model.

**Implementation guidance:**
- In `src/syntagmax/config.py`, add a new field to `ObsidianDriverConfig`:
  ```python
  contents_marker: str = Field(default='_contents_', description='Filename marker for headingless content files in publishing')
  ```
- No validation needed beyond the default Pydantic string validation.

**Test requirements:**
- Unit test: parse a config with `[drivers.obsidian] contents_marker = "_body_"` and verify `config.obsidian_driver_config.contents_marker == "_body_"`.
- Unit test: default config has `contents_marker == "_contents_"`.

**Demo:** `uv run pytest tests/test_obsidian_attachment_path.py` passes with new assertions.

### Task 2: Implement content file detection in `render_block_tree`

**Objective:** Modify the rendering loop to detect content files and skip heading emission for them, adjusting content_level accordingly.

**Implementation guidance:**
- In `render_block_tree`, after decomposing components, extract the contents marker:
  - If `config` is available: `contents_marker = config.obsidian_driver_config.contents_marker`
  - Otherwise use the default: `"_contents_"`
- After `components = decompose_file_path(...)`, check if `components` is non-empty and the last component exactly matches the marker.
- If it's a content file:
  - Emit headings for directory components normally (all except the last one).
  - Do NOT emit a heading for the file stem.
  - Set `content_level` to `path_base_level + len(components) - 1` (the directory's body level).
  - Update `last_components` to only include the directory parts (exclude the content file stem) so that sibling file headings still emit correctly.
- If it's a normal file: existing behavior unchanged.

**Test requirements:**
- Test: file named `_contents_.md` in a directory — no filename heading emitted, content renders at directory level.
- Test: `_contents_.md` sorted among siblings — content appears in correct sort position.
- Test: custom marker configured — only files with that marker are treated as content files.
- Test: file named `_contents_intro.md` does NOT match (must be exact stem match).

**Demo:** `uv run pytest tests/test_publish.py` passes with new content-file tests.

### Task 3: Add integration test with example files

**Objective:** Verify the end-to-end behavior with a realistic directory structure.

**Implementation guidance:**
- Add a test that creates a directory with:
  - `Chapter/_contents_.md` — introductory text
  - `Chapter/Requirements.md` — artifact content
- Publish with `multi_record=False` and verify:
  - `# Chapter` heading exists
  - No `_contents_` heading exists
  - Content from `_contents_.md` appears directly under `# Chapter`
  - `## Requirements` heading appears after

**Test requirements:**
- End-to-end test using manual `BlockTree` construction.
- Verify heading structure and content ordering.

**Demo:** `uv run pytest tests/test_publish.py -k content` passes.

### Task 4: Update documentation

**Objective:** Document the new feature in the configuration reference and publishing reference.

**Implementation guidance:**
- Update `docs/reference/configuration.md` to document `contents_marker` under `[drivers.obsidian]`.
- Update `docs/reference/publishing.md` to explain content file behavior.

**Test requirements:**
- No code tests; documentation review.

**Demo:** Documentation accurately describes the feature.
