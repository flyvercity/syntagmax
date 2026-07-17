# Specification: Fix H1 Heading Level to Respect File Hierarchy in Publish

## Problem Statement

In the publish pipeline, first-level Markdown headings (H1) within file content are rendered at their absolute source level instead of being offset to respect the file's hierarchical position in the document structure. A `# Heading` inside a file nested under `### filename` renders as H1, breaking the heading hierarchy of the output document.

The `render_artifact_fallback` function has the same issue — it hard-codes `start_level + 2`, which is only correct for the trivial single-component path case.

## Requirements

1. An H1 in file content must render at `file_heading_level + 1` (one level deeper than the file's own path heading).
2. Higher-level content headings (H2, H3, ...) must be offset by the same amount, preserving relative structure.
3. Artifact fallback headings must also respect the file's hierarchical level, rendering at `content_level`.
4. Direct callers of `render_block` (without `render_block_tree`) retain existing behavior via a sensible default.
5. All heading levels remain capped at 6.

## Background

### Current Behaviour

- `render_block_tree` computes file path heading levels as `path_base_level + i` where `path_base_level = start_level + 1` (multi_record) or `start_level` (single).
- `render_block` uses `pub_config.start_level` for all heading adjustments, ignoring file depth.
- `render_artifact_fallback` hard-codes `start_level + 2`, which is only coincidentally correct for single-component paths in multi_record mode.
- The formula in `process_heading_line` is `new_level = len(hashes) + (start_level - 1)`. The formula itself is correct — only the value passed needs to change.

### Example of Incorrect Output

Given record `requirements` with file at `subdir/file.md` containing `# Intro`, with `start_level=1` and multi_record:

**Current (incorrect):**
```markdown
# requirements        ← record heading at start_level
## subdir             ← path heading
### file              ← path heading
# Intro              ← WRONG: content H1 at absolute level 1
```

**Expected (correct):**
```markdown
# requirements        ← record heading at start_level
## subdir             ← path heading
### file              ← path heading
#### Intro            ← content H1 at file_level + 1
```

### Heading Level Allocation (Corrected)

- Record name heading: `start_level` (only if `multi_record=True`)
- Directory components: `path_base_level`, `path_base_level + 1`, ...
- File stem: `path_base_level + len(components) - 1`
- Content H1: `path_base_level + len(components)` (= `content_level`)
- Content H2: `content_level + 1`, etc.
- Artifact fallback heading: `content_level`
- All levels capped at 6

## Proposed Solution

### Architecture

1. Add an optional `content_level: int = None` parameter to `render_block()`.
2. When `content_level` is None, default to `pub_config.start_level` (backward compatibility for direct callers).
3. In `render_block_tree`, compute `content_level = min(6, path_base_level + len(components))` for each file.
4. Pass `content_level` to `render_block` for every block in the file.
5. Inside `render_block`, use the effective level in place of `pub_config.start_level` for all heading adjustment calls.
6. Update `render_artifact_fallback` to accept `content_level` and use it directly as the heading level (replacing `start_level + 2`).

### Content Level Computation

```python
# In render_block_tree, for each file_record:
content_level = min(6, path_base_level + len(components)) if components else path_base_level

# Pass to render_block:
render_block(block, pub_config, context, content_level=content_level)
```

### render_block Signature Change

```python
def render_block(block: Block, pub_config: PublishConfig, context: RenderContext | None = None, content_level: int | None = None) -> str:
    effective_level = content_level if content_level is not None else pub_config.start_level
    # Use effective_level everywhere pub_config.start_level was used
```

### render_artifact_fallback Change

```python
def render_artifact_fallback(artifact: Artifact, content_level: int) -> str:
    level = min(6, content_level)  # Was: min(6, start_level + 2)
    ...
```

## Task Breakdown

### Task 1: Add `content_level` parameter to `render_block` and update internal usage

**Objective:** Modify `render_block` to accept an optional `content_level` parameter and use it for all heading adjustments instead of `pub_config.start_level`.

**Implementation guidance:**
- Change signature: `render_block(block, pub_config, context=None, content_level: int | None = None)`
- At the top of the function, resolve: `effective_level = content_level if content_level is not None else pub_config.start_level`
- Replace all 4 uses of `pub_config.start_level` inside `render_block` with `effective_level`
- Update the `render_artifact_fallback` call: pass `effective_level` instead of `pub_config.start_level`
- Change `render_artifact_fallback(artifact, start_level)` to `render_artifact_fallback(artifact, content_level)` with internal logic: `level = min(6, content_level)` (remove the `+ 2`)

**Test requirements:**
- Unit test: `render_block` with explicit `content_level=4` on a `TextBlock` with `# Title` → produces `#### Title`.
- Unit test: `render_block` with explicit `content_level=3` on an `ArtifactBlock` without custom render → artifact heading is `###`.
- Unit test: `render_block` with `content_level=None` falls back to `pub_config.start_level` behavior.

**Demo:** `render_block(TextBlock(content='# Heading'), pub_config, content_level=4)` produces `#### Heading`.

### Task 2: Compute and pass `content_level` in `render_block_tree`

**Objective:** In the main rendering loop, compute the effective content level for each file based on its hierarchical depth and pass it to `render_block`.

**Implementation guidance:**
- After computing `components` for a file, calculate: `content_level = min(6, path_base_level + len(components))` if components is non-empty, else `path_base_level`.
- Pass to `render_block`: `render_block(block, pub_config, context, content_level=content_level)`

**Test requirements:**
- Integration test: multi_record tree, file at `subdir/file.md` with `# Intro` → output has `#### Intro` (record=1, subdir=2, file=3, content=4).
- Integration test: single-record, file at `dir/file.md` with `# Intro` → output has `### Intro` (dir=1, file=2, content=3).
- Level capping test: deep path + heading → capped at H6.
- Empty components edge case → content_level = path_base_level.

**Demo:** Full rendering pipeline produces properly nested headings matching the document hierarchy.

### Task 3: Update existing test assertions for corrected behavior

**Objective:** Fix all test assertions that validated the old (incorrect) heading levels.

**Implementation guidance:**
- `test_render_basic` (line 80): Change `assert '# Intro' in result` → `assert '### Intro' in result` (file `req.md` = 1 component, multi_record, start_level=1 → path_base=2, content_level=3).
- `test_render_basic` (line 81): `assert '### REQ-1' in result` — **stays the same** (content_level=3, artifact fallback at level 3).
- Verify `test_publish_cli_basic` and all `TestPathHeadings` tests remain unchanged (no content headings to adjust).

**Test requirements:**
- Full test suite passes: `uv run pytest tests/`
- Linter clean: `uv run ruff check .`

**Demo:** All tests pass with corrected assertions.

### Task 4: Add edge-case handling and documentation

**Objective:** Handle edge cases and add code comments documenting the heading hierarchy model.

**Implementation guidance:**
- Edge case: files with no path components → content_level = path_base_level.
- Edge case: H6 in source with deep nesting → capped at 6.
- Add docstring to `render_block` documenting the `content_level` parameter.
- Add a brief comment in `render_block_tree` explaining the heading hierarchy model.

**Test requirements:**
- Test content with `###### Deep` in a file at path depth 2 → still produces `######`.
- Test empty components edge case.

**Demo:** Edge cases handled gracefully; `uv run pytest tests/` passes.
