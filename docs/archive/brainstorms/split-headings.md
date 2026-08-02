# Brainstorm: Extracting Headers as Separate Text Blocks

## User Feedback

If in input Markdown only headers change, the change report outputs the whole text block as changed. This is deemed inconvenient. The idea is to extract headers (outside artifacts) as separate non-artifact text blocks inside the Markdown driver. It will split some text blocks into a list of blocks, but shall solve the initial issue.

## Current Architecture

### How Text Blocks Are Formed

The Markdown extractor (`_extract_blocks_from_markdown`) captures all text between artifact markers as a single `TextBlock`. After initial extraction, a marker-splitting pass (`_split_text_block_by_markers`) breaks blocks by user-defined fragment markers (`[COM]`, `[NOTE]`, etc.). Remaining unmarked text stays as monolithic blocks.

### How Text Blocks Are Diffed

`compare_text_blocks` in `change_diff.py` groups text blocks by file path, then:
1. Matches blocks by explicit ID (if `block.explicit_id` is set).
2. For remaining unmatched blocks, uses `difflib.SequenceMatcher` on content to align by similarity.
3. Reports added/removed/modified fragments.

The comparison is atomic per block — any change within a block marks the entire block as modified.

### The Problem in Practice

```markdown
## System Overview          ← user changes this to "## System Architecture"

This is a long paragraph
of detailed text that
hasn't changed at all.

Another paragraph here
describing something.
```

Current extraction: one `TextBlock` containing both heading + body. Change report shows the whole thing as modified.

---

## Design Options

### Option A: Split at Extraction Time (Post-Processing Pass)

Add a pass similar to the existing `_split_text_block_by_markers` logic — after marker splitting, iterate remaining unmarked `TextBlock`s and split on heading boundaries.

A `TextBlock` like:
```
## Heading\n\nParagraph text\n\nMore text\n
```
becomes:
```
TextBlock(content="## Heading\n", marker=None)
TextBlock(content="\nParagraph text\n\nMore text\n", marker=None)
```

**Pros:**
- Minimal impact on diff logic — it already matches by position/content.
- Reuses the established pattern (post-extraction split pipeline).
- Heading blocks are small, so positional matching in `compare_text_blocks` works well.

**Cons:**
- Increases the number of text blocks per file (more blocks to match).
- Heading blocks without explicit IDs rely on positional matching (SequenceMatcher), which could be fragile if headings are reordered.

---

### Option B: Give Heading Blocks an Implicit Stable ID

Derive an implicit ID from the heading text itself (slug). E.g. `## System Overview` → ID `h-system-overview`. This enables ID-based matching in `_match_text_blocks`.

**Pros:**
- Robust matching even if headings move within a file.
- Renaming a heading is correctly reported as a modification (old ID not found → removed, new ID → added — or same positional match shows modification).

**Cons:**
- Renaming *is* what we want to detect, so using heading text as a stable ID defeats purpose. A renamed heading would appear as "added + removed" rather than "modified".
- Headings are inherently unstable identifiers.

**Verdict:** Don't use heading-derived IDs. Positional matching is better here.

---

### Option C: Use a Synthetic Marker (e.g. `HEADING`)

Emit heading blocks as `TextBlock(content="## Heading", marker="HEADING")`. This signals to the diff engine that these are structurally distinct.

**Pros:**
- Differentiates headings from body text in the change report rendering.
- The report can show "Heading changed" vs. "Text block changed".

**Cons:**
- `marker` field currently implies user-defined markers (`[COM]`, `[NOTE]`). Overloading it for internal purposes might confuse plugin authors.
- Requires change_render adjustments to display heading changes differently.

---

### Option D: New `HeadingBlock` Subclass

Introduce a dedicated `HeadingBlock(Block)` dataclass with `level: int` and `content: str` fields.

**Pros:**
- Clean separation of concerns. Explicitly typed.
- Downstream consumers (publish, change report, metrics) can handle headings specifically.

**Cons:**
- Bigger change surface: every place that iterates `Block` types needs updating.
- Publish pipeline already emits headings from `TextBlock.content` — would require migration.
- Overkill if the only motivation is better change reports.

---

## Recommended Approach: Option A with a Twist from C

1. **Split headings out as separate `TextBlock` instances** in a new post-processing pass in `_extract_blocks_from_markdown` (after marker splitting).

2. **Use `marker="HEADING"` (or `marker="H"`)** on the split heading blocks. This:
   - Allows the change report renderer to label them distinctively.
   - Doesn't conflict with user markers (user markers come from config, `HEADING` is reserved/internal).
   - Enables future filtering (e.g. `--include-non-artifact` could optionally suppress headings).

3. **Splitting logic:**
   - Iterate remaining unmarked `TextBlock`s (where `block.marker is None`).
   - Scan line-by-line; when a line matches `^\s*#{1,6}\s`, end the current text accumulator as one block, emit the heading line as a separate block, start a new accumulator.
   - Preserve `source_offset` accounting.
   - Be code-block-aware: headings inside fenced code blocks are not split.

4. **`TextBlock.id` for headings:** Leave as `None` (no explicit ID). The SequenceMatcher alignment in `compare_text_blocks` will handle matching by content similarity, which is the right behaviour — a renamed heading appears as "modified" (content changed).

---

## Impact on Other Subsystems

| Subsystem | Impact |
|-----------|--------|
| **Change report diff** | Transparent — already handles multiple text blocks per file. Smaller blocks = more precise diffs. |
| **Change report render** | Minor: can optionally render heading changes with a "Heading changed" label if `marker == "HEADING"`. |
| **Publish** | Transparent — publish iterates blocks and renders `TextBlock.content` as-is. Headings still render correctly. |
| **Metrics** | No impact (doesn't count text blocks). |
| **Edit attrs / edit markers** | No impact (operates on `ArtifactBlock` or marker-tagged blocks; won't touch `HEADING`-marked blocks unless explicitly requested). |
| **Obsidian soft line breaks** | No impact (operates on all `TextBlock`s regardless of marker). |
| **`exclude_elements` filter** | Needs care: if headings are excluded *and* split, the filter should still work. Current filter removes heading lines from content — if the heading is its own block, the filter would remove the entire block. This is actually cleaner. |

---

## Edge Cases

- **Heading immediately followed by another heading** (no body between): Produces two consecutive heading blocks. Fine.
- **Heading at very start of file** (before any artifact): Correctly splits into heading block + body block.
- **Heading inside a fenced code block**: Must *not* be split out. The splitting pass needs to track code-fence state.
- **Heading inside a marked fragment** (`[COM]...heading...[/COM]`): These blocks already have `marker != None` and would be skipped by the splitting pass. Correct behaviour.
- **YAML frontmatter**: Already stripped before this pass runs (via `exclude_elements`). No issue.
- **Setext headings** (`===` / `---` underlines): Rare in Obsidian, but could be supported by detecting the two-line pattern. Suggest deferring this unless users report it.

---

## Configuration Considerations

Consider making this opt-in or opt-out via a config flag:

```toml
[change]
split_headings = true  # default true
```

Or unconditionally active (simpler, and the only downside is more blocks — which is arguably better for all consumers).

**Recommendation:** Make it unconditional. The additional blocks have negligible performance impact and improve granularity everywhere.

---

## Summary

The cleanest path:
1. Add a `_split_headings` post-processing pass in `MarkdownExtractor._extract_blocks_from_markdown`, after the marker-splitting pass.
2. Emit heading lines as `TextBlock(content="## ...\n", marker="HEADING", source_offset=...)`.
3. No changes to the diff algorithm — smaller blocks naturally produce more precise change reports.
4. Optionally enhance `change_render` to label heading changes distinctively.
