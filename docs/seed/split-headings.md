# Split Headings as Separate Text Blocks

## Problem

When only a heading changes in an input Markdown file (outside artifacts), the change report flags the entire surrounding text block as modified. This is noisy and inconvenient — users want to see that only the heading changed, not the whole paragraph below it.

## Root Cause

The Markdown extractor captures all text between artifacts as a single `TextBlock`. The change report diffs text blocks atomically, so any modification within the block (even a single heading line) marks the whole block as changed.

## Proposed Solution

Extract headings (outside artifacts) as separate `TextBlock` instances during Markdown extraction. This splits some text blocks into a list of blocks but makes the change report granular enough to show only what actually changed.

## Design Notes

- Add a post-processing pass in `MarkdownExtractor._extract_blocks_from_markdown`, after the existing marker-splitting pass.
- Iterate remaining unmarked `TextBlock`s (where `block.marker is None`).
- Scan line-by-line; when a line matches `^\s*#{1,6}\s`, split it out as a separate block.
- Use `marker="HEADING"` on the split heading blocks to distinguish them from body text.
- Be code-block-aware: headings inside fenced code blocks must not be split.
- Preserve `source_offset` accounting.
- Leave `TextBlock.id` as `None` — positional matching (SequenceMatcher) in `compare_text_blocks` handles renamed headings correctly (shows as "modified").
- Make this unconditional (no config flag). More blocks have negligible performance cost and improve granularity everywhere.

## Impact on Other Subsystems

| Subsystem | Impact |
|-----------|--------|
| Change report diff | Transparent — already handles multiple text blocks per file. Smaller blocks = more precise diffs. |
| Change report render | Minor: can optionally label heading changes distinctively if `marker == "HEADING"`. |
| Publish | Transparent — iterates blocks and renders `TextBlock.content` as-is. |
| Metrics | No impact. |
| Edit attrs / edit markers | No impact (operates on `ArtifactBlock` or user-marker-tagged blocks). |
| Obsidian soft line breaks | No impact (operates on all `TextBlock`s regardless of marker). |
| `exclude_elements` filter | Cleaner: if headings are excluded, the filter removes the entire heading block rather than stripping lines from a larger block. |

## Edge Cases

- **Consecutive headings** (no body between): Two consecutive heading blocks. Fine.
- **Heading at file start**: Correctly splits into heading block + body block.
- **Heading inside fenced code block**: Must NOT be split. Splitting pass must track fence state.
- **Heading inside a marked fragment** (`[COM]...heading...[/COM]`): Skipped — these blocks already have `marker != None`.
- **Setext headings** (`===`/`---` underlines): Defer unless users report. Rare in Obsidian.

## Follow-up Tasks

- Amend README and docs/reference/obsidian.md to document the heading block behaviour.
- Optionally enhance `change_render.py` to label heading changes with a distinct prefix in the report.
- Add test cases for heading splitting (consecutive headings, code-block-aware, mixed with markers).
