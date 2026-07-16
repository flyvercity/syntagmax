# Split Headings as Separate Text Blocks

## Problem Statement

When only a heading changes in an input Markdown file (outside artifacts), the change report flags the entire surrounding text block as modified. This is noisy and inconvenient — users expect precision: only the heading should appear as changed, not the entire paragraph block beneath it.

## Requirements

1. ATX-style headings (`#` through `######`) outside artifacts are extracted as individual `TextBlock` instances with `marker="HEADING"`.
2. Heading splitting is code-block-aware: headings inside fenced code blocks (```` ``` ````) must not be split.
3. `source_offset` is correctly preserved for all resulting blocks.
4. No explicit `id` on heading blocks — positional/content matching in `compare_text_blocks` handles diffs.
5. The behaviour is unconditional (no configuration flag).
6. The change report renderer labels heading changes as "Heading" instead of "Text fragment".
7. The `exclude_elements` filter correctly handles pre-split heading blocks.
8. Existing tests remain green.
9. No impact on publish, metrics, edit attrs, or edit markers subsystems.

## Background

### How Text Blocks Are Formed

`MarkdownExtractor._extract_blocks_from_markdown` (line ~852 in `src/syntagmax/extractors/markdown.py`) captures all text between artifact markers as a single `TextBlock`. After initial extraction, a marker-splitting pass (`_split_text_block_by_markers`, line ~925) breaks blocks by user-defined fragment markers (`[COM]`, `[NOTE]`, etc.). Remaining unmarked text stays as monolithic blocks.

### How Text Blocks Are Diffed

`compare_text_blocks` in `src/syntagmax/change_diff.py` groups text blocks by file path, then:
1. Matches blocks by explicit ID (if `block.explicit_id` is set).
2. For remaining unmatched blocks, uses `difflib.SequenceMatcher` on content to align by similarity.
3. Reports added/removed/modified fragments.

The comparison is atomic per block — any change within a block marks the entire block as modified.

### Element Filters

`_apply_element_filters` runs *after* `_extract_blocks_from_markdown` returns. It operates on individual `TextBlock` instances. With heading splitting, heading blocks become standalone — the filter can drop or transform them individually rather than stripping lines from a larger block.

### Change Report Rendering

`_render_text_fragment` in `src/syntagmax/change_render.py` (line 335) renders `TextFragmentChange` objects. The `marker` field is available on the change object but not currently used in the heading label. The enhancement point is to check `change.marker == "HEADING"` and use a distinct label.

### Test Patterns

Tests use `tmp_path`, `Config`, `InputRecord`, and `ObsidianExtractor` fixtures (see `tests/test_marked_fragments.py`, `tests/test_extractors.py`). Change report integration tests use `git.Repo.init`, `CliRunner`, and the syntagmax CLI (see `tests/test_change_report.py`).

## Proposed Solution

```mermaid
flowchart TD
    A[_extract_blocks_from_markdown] --> B[Initial block list]
    B --> C{markers configured?}
    C -->|Yes| D[_split_text_block_by_markers]
    C -->|No| E[_split_headings]
    D --> E[_split_headings]
    E --> F[Return blocks]
    F --> G[_apply_element_filters]
    G --> H[Final block list]
```

### Data Model

No new dataclasses. Heading blocks are `TextBlock` instances with:
- `content`: The heading line including the `#` prefix and trailing newline.
- `marker`: `"HEADING"` (reserved internal marker name).
- `id`: `None`.
- `explicit_id`: `False`.
- `source_offset`: Correct character offset in the source file.

### Splitting Algorithm

```python
def _split_headings(self, blocks: list[Block]) -> list[Block]:
    """Split ATX headings out of unmarked TextBlocks as separate heading blocks."""
    result: list[Block] = []
    heading_re = re.compile(r'^(\s*#{1,6}\s)')

    for block in blocks:
        if not isinstance(block, TextBlock) or block.marker is not None:
            result.append(block)
            continue

        lines = block.content.splitlines(keepends=True)
        base_offset = block.source_offset
        accumulator: list[str] = []
        acc_offset = base_offset
        in_code_block = False

        for line in lines:
            stripped = line.lstrip()

            # Track fenced code block state
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                accumulator.append(line)
                continue

            if in_code_block:
                accumulator.append(line)
                continue

            if heading_re.match(line):
                # Flush preceding text
                if accumulator:
                    text = ''.join(accumulator)
                    if text.strip():
                        result.append(TextBlock(content=text, source_offset=acc_offset))
                    accumulator = []

                # Emit heading block
                heading_offset = (base_offset + sum(len(l) for l in lines[:lines.index(line)])) if base_offset is not None else None
                result.append(TextBlock(content=line, marker='HEADING', source_offset=heading_offset))
                acc_offset = (heading_offset + len(line)) if heading_offset is not None else None
            else:
                if not accumulator and base_offset is not None:
                    acc_offset = base_offset + sum(len(l) for l in lines[:lines.index(line)])
                accumulator.append(line)

        # Flush remaining text
        if accumulator:
            text = ''.join(accumulator)
            if text.strip():
                result.append(TextBlock(content=text, source_offset=acc_offset))

    return result
```

*Note: The actual implementation should compute offsets incrementally rather than using `lines.index()` for performance.*

### Change Render Enhancement

In `_render_text_fragment`:

```python
if change.marker == 'HEADING':
    label = _('Heading')
else:
    label = _('Text fragment')
lines = [f'##### {label} ({_(change.status.value)})', '']
```

## Task Breakdown

### Task 1: Implement `_split_headings` in `MarkdownExtractor`

**Objective:** Add a method that iterates unmarked `TextBlock`s and splits ATX headings into separate blocks with `marker="HEADING"`.

**Implementation guidance:**
- File: `src/syntagmax/extractors/markdown.py`
- Add `_split_headings(self, blocks: list[Block]) -> list[Block]` method.
- Logic: iterate blocks; skip non-`TextBlock` or blocks with `marker is not None`; for qualifying blocks scan lines tracking fenced-code state; on heading line flush accumulator as `TextBlock(marker=None)`, emit heading as `TextBlock(marker="HEADING")`.
- Wire it at the end of `_extract_blocks_from_markdown`, after the marker-splitting pass (unconditionally, regardless of whether markers are configured).
- Compute `source_offset` incrementally (maintain a running character position per block).

**Test requirements:** Unit tests in `tests/test_heading_split.py`:
- Single heading at start of block → heading + body.
- Multiple headings → multiple heading blocks with body blocks between them.
- Heading inside fenced code block → NOT split.
- Consecutive headings → consecutive heading blocks, no empty body blocks.
- Empty/whitespace-only body between headings → no spurious empty TextBlocks.
- `source_offset` is correctly computed for each resulting block.
- Blocks with `marker != None` (e.g. `"COM"`) are not processed.

**Demo:** `uv run pytest tests/test_heading_split.py -v`

---

### Task 2: Integrate with element filters

**Objective:** Ensure `_apply_element_filters` correctly handles pre-split heading blocks.

**Implementation guidance:**
- File: `src/syntagmax/extractors/markdown.py`, method `_apply_element_filters`.
- When `headings` is in `exclude_elements` and block has `marker == "HEADING"`:
  - Mode `string` / `string-on-start`: Drop the block entirely (skip it).
  - Mode `only`: Strip the `#` prefix from content (convert heading to plain text), change marker back to `None`.
- The existing `if content and content.strip()` check already handles empty blocks.

**Test requirements:** Add cases in `tests/test_heading_split.py` or `tests/test_exclude_tags.py`:
- `headings` exclusion mode `string` drops heading blocks.
- `headings` exclusion mode `only` converts heading blocks to plain text blocks.
- Body text blocks adjacent to removed headings are unaffected.

**Demo:** `uv run pytest tests/test_heading_split.py tests/test_exclude_tags.py -v`

---

### Task 3: Enhance change report renderer

**Objective:** Label heading changes as "Heading" in the change report.

**Implementation guidance:**
- File: `src/syntagmax/change_render.py`, function `_render_text_fragment` (line 335).
- Check `change.marker == 'HEADING'`; use `_("Heading")` as label, else `_("Text fragment")`.
- Add `"Heading"` to locale files:
  - `src/syntagmax/resources/locales/en/LC_MESSAGES/messages.po`
  - `src/syntagmax/resources/locales/ru/LC_MESSAGES/messages.po` (translate as `"Заголовок"`)
- Recompile `.mo` files.

**Test requirements:** Add a test in `tests/test_change_report.py`:
- Create a repo with a file containing a heading + body text + artifact.
- Commit, then modify only the heading, commit again.
- Run `change report --base HEAD~1 --target HEAD`.
- Assert output contains "Heading" (or localised equivalent) and NOT the full body text.

**Demo:** `uv run pytest tests/test_change_report.py -v`

---

### Task 4: End-to-end verification

**Objective:** Verify the full pipeline with the example project and full test suite.

**Implementation guidance:**
- Run `uv run syntagmax --render-tree --cwd ./example/obsidian-driver/ analyze` — confirm no regressions; heading blocks appear as separate entries if tree rendering shows text blocks.
- Run full test suite.
- Run linter.

**Test requirements:**
- `uv run pytest tests -v` — all tests pass.
- `uv run ruff check src tests` — clean.

**Demo:** All green.

---

### Task 5: Documentation update

**Objective:** Document the heading block behaviour.

**Implementation guidance:**
- `docs/reference/obsidian.md`: Add a subsection after the existing "Text Blocks" / "Overview" section explaining that headings are automatically extracted as separate text blocks with `marker="HEADING"`. Mention: code-block awareness, no configuration needed, improves change report granularity.
- `README.md`: No change needed (the feature is transparent; no new CLI flags or config).
- `docs/reference/configuration.md`: No change needed (no new config option).

**Test requirements:** N/A.

**Demo:** Documentation reads coherently and accurately describes the new behaviour.
