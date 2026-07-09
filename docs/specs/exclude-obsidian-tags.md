# Spec: Exclude Obsidian Inline Tags from TextBlocks

## Problem Statement

Obsidian inline tags (`#tag`, `#nested/tag`) appear in Markdown body text and get passed through to published output. Users need the ability to strip these tags from `TextBlock` content during extraction, consistent with the existing `exclude_elements` mechanism for callouts, frontmatter, headings, and horizontal rules.

## Requirements

- Add `tags` as a new valid value for `exclude_elements` configuration
- When enabled, strip all inline Obsidian `#tag` occurrences from `TextBlock` content
- Only affect text blocks (not artifact content inside `[REQ]...[/REQ]`)
- Respect fenced code blocks (never strip tags inside ` ``` ` fences)
- Handle all valid Obsidian tag formats: `#simple`, `#nested/tag`, `#with-hyphens`, `#with_underscores`, `#Unicode≥U+0080`
- Must not match headings (`# Heading`) or hex color codes (`#fff`, `#123456`)
- Configurable at both global (`[drivers.obsidian]`) and per-input-record level
- Seamless with existing workflows (no breaking changes)

## Background

- The `exclude_elements` system is already well-established in `config.py` with a `VALID_EXCLUDE_ELEMENTS` frozenset and Pydantic validation
- Filtering logic lives in `MarkdownExtractor._filter_text_content()` which operates line-by-line for most filters, but handles frontmatter as a block
- Tags are inline (not line-level), so a regex substitution approach is needed rather than line skipping
- Obsidian tag rules: must start with a letter, underscore, or Unicode ≥ U+0080 after `#`; can contain letters, numbers, `_`, `-`, `/`; cannot start with a digit

## Proposed Solution

1. Add `'tags'` to `VALID_EXCLUDE_ELEMENTS` in `config.py`
2. Extend `_filter_text_content()` in `markdown.py` to strip inline `#tag` patterns when `'tags'` is in the exclude list
3. Use a regex that correctly identifies Obsidian tags while avoiding false positives (headings, hex codes, code blocks)
4. Add unit tests covering normal tags, nested tags, edge cases (headings, code blocks, hex colors), and configuration validation

## Task Breakdown

### Task 1: Add `tags` to valid exclude elements and update configuration validation

- **Objective:** Register `'tags'` as a recognized value in the exclude_elements system
- **Implementation guidance:**
  - Add `'tags'` to the `VALID_EXCLUDE_ELEMENTS` frozenset in `src/syntagmax/config.py`
- **Test requirements:** Write a test confirming `'tags'` is accepted in config validation and that invalid values are still rejected
- **Demo:** Config parsing accepts `exclude_elements = ["tags"]` without error

### Task 2: Implement tag stripping regex in `_filter_text_content()`

- **Objective:** Strip inline Obsidian tags from text content when `'tags'` is in exclude list
- **Implementation guidance:**
  - Add a tag-stripping pass in `MarkdownExtractor._filter_text_content()` (in `src/syntagmax/extractors/markdown.py`)
  - The regex should match: `#` followed by a letter, `_`, or Unicode char ≥ U+0080, then any combination of letters, digits, `_`, `-`, `/`
  - Pattern suggestion: `r'(?<![&\w])#(?=[^\d\s])[\w\-/]+'` or similar, refined to avoid matching headings (which start at BOL with `# `) and hex codes
  - Process inline (not line-by-line) since tags can appear mid-line
  - Must be code-block-aware: split content at fence boundaries and only filter non-fenced segments (reuse the existing `in_code_block` tracking or apply a similar segment approach)
  - Strip trailing whitespace that would result in double spaces after tag removal
- **Test requirements:**
  - Tags like `#safety`, `#project/active`, `#my_tag`, `#task-123` are stripped
  - Headings (`# Title`, `## Section`) are NOT stripped
  - Hex color codes (`#fff`, `#123abc`) are NOT stripped (digit after `#`)
  - Tags inside fenced code blocks are preserved
  - Tags at start of line, mid-line, and end of line all work
  - Multiple tags on the same line are all stripped
  - Nested tags (`#parent/child/grandchild`) are stripped as a unit
- **Demo:** A markdown file with `Some text #safety and #performance/telemetry here` produces `Some text and here` (with cleaned up spacing)

### Task 3: Integration test with full extraction pipeline

- **Objective:** Verify the feature works end-to-end through config → extraction → block filtering
- **Implementation guidance:**
  - Write an integration-style test that creates a config with `exclude_elements = ["tags"]`, creates a markdown file with mixed content (tags in text, tags in code blocks, headings), and verifies the extracted blocks have tags removed from TextBlocks only
  - Verify that artifact blocks (inside `[REQ]...[/REQ]`) are NOT affected
- **Test requirements:**
  - Full config-driven extraction produces correct results
  - Tags in TextBlocks are stripped
  - Artifact content is untouched
  - Combining `tags` with other exclude elements (e.g., `["callouts", "tags"]`) works correctly
- **Demo:** `ObsidianExtractor.extract_blocks_from_file()` on a file with tags produces blocks where TextBlock content has no inline `#tag` occurrences

### Task 4: Update documentation

- **Objective:** Document the new `tags` exclude element in config reference
- **Implementation guidance:**
  - Add `tags` to the valid values list in `docs/reference/configuration.md`
  - Add description: `tags` — inline Obsidian tags (`#tag`, `#nested/tag`)
  - Add an example showing usage
- **Test requirements:** N/A (documentation)
- **Demo:** Documentation accurately describes the new option with examples
