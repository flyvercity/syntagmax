# Specification: Content Files (Headingless File Rendering)

## Problem Statement

The publishing engine uses each file's stem as a heading in the output. Users need a way to designate certain files as "content files" that contribute their content directly at the parent directory's heading level, without generating their own heading. The file participates in normal sort order alongside siblings.

## Requirements

1. Files whose stem matches the configurable marker (default `_contents_`, case-insensitive) are treated as content files.
2. Content files are sorted normally with their siblings (alphabetically by path).
3. Content files do NOT emit a filename heading — their blocks render at the directory's own body level (same `content_level` as the directory heading itself, not one level deeper).
4. The marker is configurable via `PublishConfig` (in `publish.yaml`): `contents_marker: "_contents_"`.
5. The feature only affects the publish pipeline's heading emission, not extraction.
6. The marker must be a non-empty string without directory separator characters (`/`, `\`).

## Background

- `render_block_tree` in `publish.py` iterates files, calls `decompose_file_path` to split path into components, then emits a heading for each new component (including file stem as the last component).
- `content_level` is computed as `path_base_level + len(components)` — one deeper than the file's own heading.
- `PublishConfig` in `publish_config.py` holds per-record publishing options (`start_level`, `remove_numeric_prefixes_in_headers`, `include_plain_text`, `render`, etc.) and is the natural home for `contents_marker` since the feature is driver-agnostic.
- The publish config is accessible in `render_block_tree` via `config.load_publish_config(record)`.

## Proposed Solution

### Architecture

1. Add `contents_marker: str` field to `PublishConfig` (default `"_contents_"`) with a validator ensuring it is non-empty, non-whitespace, and contains no directory separators (`/`, `\`).
2. In `render_block_tree`, after decomposing path components, check if the last component (file stem) matches the contents marker case-insensitively. If so:
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
contents_marker = pub_config.contents_marker  # from PublishConfig

# After decompose_file_path:
is_content_file = bool(components) and components[-1].lower() == contents_marker.lower()
```

The match is case-insensitive against the file stem. A file named `_contents_intro.md` does NOT match because the stem `_contents_intro` != `_contents_`.

## Task Breakdown

### Task 1: Add `contents_marker` option to `PublishConfig`

**Objective:** Add the configurable marker string to the publish config model with validation.

**Implementation guidance:**
- In `src/syntagmax/publish_config.py`, add a new field to `PublishConfig`:
  ```python
  contents_marker: str = Field(default='_contents_', description='Filename marker for headingless content files in publishing')
  ```
- Add a Pydantic `field_validator` that rejects empty/whitespace-only values and values containing `/` or `\`.

**Test requirements:**
- Unit test: load a `publish.yaml` with `contents_marker: "_body_"` and verify `pub_config.contents_marker == "_body_"`.
- Unit test: default `PublishConfig()` has `contents_marker == "_contents_"`.
- Unit test: validation rejects empty string, whitespace, and strings with `/` or `\`.

**Demo:** `uv run pytest tests/test_publish_config.py` passes with new assertions.

### Task 2: Implement content file detection in `render_block_tree`

**Objective:** Modify the rendering loop to detect content files and skip heading emission for them, adjusting content_level accordingly.

**Implementation guidance:**
- In `render_block_tree`, `pub_config` is already loaded per input block. Use `pub_config.contents_marker` directly.
- After `components = decompose_file_path(...)`, check if `components` is non-empty and the last component matches the marker case-insensitively (`components[-1].lower() == pub_config.contents_marker.lower()`).
- If it's a content file:
  - Emit headings for directory components normally (all except the last one).
  - Do NOT emit a heading for the file stem.
  - Set `content_level` to `path_base_level + len(components) - 1` (the directory's body level).
  - Update `last_components` to only include the directory parts (exclude the content file stem) so that sibling file headings still emit correctly.
- If it's a normal file: existing behavior unchanged.

**Test requirements:**
- Test: file named `_contents_.md` in a directory — no filename heading emitted, content renders at directory level.
- Test: file named `_CONTENTS_.md` — still matches (case-insensitive).
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

**Objective:** Document the new feature in the publishing reference.

**Implementation guidance:**
- Update `docs/reference/publishing.md` to document `contents_marker` as a `publish.yaml` option and explain content file behavior.
- Update `docs/reference/configuration.md` if it references publish options.

**Test requirements:**
- No code tests; documentation review.

**Demo:** Documentation accurately describes the feature.
