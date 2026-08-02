# Spec Critique: Split Headings as Separate Text Blocks

- **Target Specification:** [docs/specs/split-headings.md](../specs/split-headings.md)
- **Date:** 2026-07-16
- **Reviewers:** Antigravity (Product & Engineering Lenses)

---

## Executive Summary

The proposed specification introduces a valuable feature to split ATX-style headings outside of artifacts into their own standalone `TextBlock` instances with a `"HEADING"` marker. This improves change report granularity by ensuring that modifying a heading does not flag the entire subsequent paragraph/block as modified.

However, our review identified several critical engineering bugs and integration issues that must be addressed before proceeding:
1. **Duplicate Line Offset Corruption:** The proposed `_split_headings` logic uses `lines.index(line)` to compute source offsets. If a markdown file contains duplicate lines, this will resolve the offset of the first occurrence, corrupting offset tracking for all subsequent duplicates.
2. **Renumber Markers subsystem conflict:** Because `"HEADING"` blocks have a non-None marker, the `renumber` CLI command will attempt to process them. Since they lack brackets, they will cause spammy warnings in the console for every heading in the file.
3. **Publishing include_plain_text bypass:** Since `"HEADING"` blocks have a marker, they bypass the `include_plain_text: false` configuration during publishing, forcing headings to render even when plain text is disabled.
4. **CommonMark compliance:** The proposed heading regex allows any amount of leading whitespace, which violates CommonMark rules where headings are limited to at most 3 leading spaces.

We recommend updating the specification to fix these issues.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Product Lens Findings

### 1d. Edge Cases & User Experience
* **P1: Whitespace-only block filtering (Severity: 💡 Recommendation)**
  - **Finding:** In the proposed `_split_headings` function, empty or whitespace-only text blocks between headings are dropped via `if text.strip():`. This means vertical spacing (e.g. consecutive newlines) between headings or blocks will be permanently discarded from the block list. When publishing, this results in loss of formatting/blank lines in the generated output.
  - **Suggestion:** Do not drop whitespace-only blocks; preserve blocks containing newlines to maintain formatting fidelity.

### 1e. Success Measurement / Configuration
* **P2: Lack of Configuration Toggle (Severity: 🤔 Question)**
  - **Finding:** The behavior is defined as unconditional. While highly useful, some users may rely on headings being grouped with their corresponding paragraphs for third-party tools or custom filter plugins.
  - **Suggestion:** Clarify if an optional configuration flag (e.g., `split_headings = true` under project config) should be supported, or if unconditional splitting is preferred.

---

## Engineering Lens Findings

### 2a. Architecture Soundness & Performance
* **E1: Duplicate Line Offset Corruption (Severity: 🎯 Must-Address)**
  - **Finding:** The expression `lines.index(line)` inside `_split_headings` searches the entire list from the beginning. If the document has duplicate lines, it will always return the index of the first occurrence, leading to incorrect offset values for subsequent duplicates.
  - **Suggestion:** Use a running character offset accumulator (`current_offset`) incremented by `len(line)` on each iteration.

* **E4: CommonMark Compliance for Headings (Severity: 💡 Recommendation)**
  - **Finding:** The proposed regex `heading_re = re.compile(r'^(\s*#{1,6}\s)')` matches lines with 4 or more leading spaces. Under standard CommonMark, lines with 4 or more leading spaces are treated as indented code blocks rather than headings.
  - **Suggestion:** Restrict leading spaces to at most 3 using `heading_re = re.compile(r'^([ ]{0,3}#{1,6}\s)')`.

### 2g. Dependencies & Integration Risks
* **E2: Marker Renumbering Command Warnings (Severity: 🎯 Must-Address)**
  - **Finding:** In `src/syntagmax/edit_markers.py`, the marker renumbering logic processes any `TextBlock` with a non-None marker. Since split headings will have `marker="HEADING"`, the renumbering logic will try to edit them. Since headings do not start with `[`, `_compute_tag_replacement` will return `None`, printing a warning to the logs for every heading: `Could not find opening tag for [HEADING] at offset ...`.
  - **Suggestion:** Update `edit_markers.py` to skip blocks whose marker is not in `record.markers` (user-configured markers).

* **E3: Plain Text Exclusion Bypass during Publishing (Severity: 🎯 Must-Address)**
  - **Finding:** In `src/syntagmax/publish.py`, `render_block` checks `if marker is not None:` to identify marked blocks. Since headings will have `marker="HEADING"`, they bypass the `if not pub_config.include_plain_text: return ''` check, causing headings to render even when `include_plain_text = false`.
  - **Suggestion:** In `render_block`, set `marker = None` if `marker == "HEADING"` to correctly process headings as unmarked text blocks.

---

## Cross-Lens Synthesis

* **X1: Correct Block Splitting and Preservation (Severity: 🎯 Must-Address)**
  - *Product Perspective:* Ensuring vertical spacing/newlines between headings are not dropped avoids visual changes/loss of formatting in published documents.
  - *Engineering Perspective:* Computing offsets incrementally resolves a critical correctness bug for files containing duplicate lines.
* **X2: Subsystem Isolation (Severity: 🎯 Must-Address)**
  - *Product Perspective:* Users running standard commands like `renumber` should not see cryptic errors or warnings about headings.
  - *Engineering Perspective:* Preventing `"HEADING"` from triggering renumber and publishing checks ensures the new feature remains self-contained and free of side effects.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 💡 | Edge Cases | Empty lines between consecutive headings are discarded. | Preserve whitespace-only text blocks in `_split_headings` or ensure newlines are retained. |
| P2 | Product | 🤔 | Configuration | Heading splitting is unconditional and lacks a configuration toggle. | Clarify if a configuration toggle is needed or if unconditional behavior is acceptable. |
| E1 | Engineering | 🎯 | Failure Modes | `lines.index(line)` causes incorrect offset calculations for duplicate lines. | Compute offsets incrementally using a running character accumulator. |
| E2 | Engineering | 🎯 | Integration | `"HEADING"` blocks cause spammy warnings in `renumber_markers`. | Update `edit_markers.py` to skip text blocks whose marker is not in `record.markers`. |
| E3 | Engineering | 🎯 | Integration | `"HEADING"` blocks bypass the `include_plain_text` publish filter. | Update `render_block` in `publish.py` to treat `"HEADING"` blocks as unmarked (set `marker = None`). |
| E4 | Engineering | 💡 | Architecture | Heading regex allows too many leading spaces, violating CommonMark rules. | Restrict leading spaces to 0-3 using `^([ ]{0,3}#{1,6}\s)`. |

---

## Verdict & Offer of Remediation

### Verdict: ⚠️ **PROCEED WITH UPDATES**

To address the findings and recommendations, we suggest editing [docs/specs/split-headings.md](../specs/split-headings.md) with the following updates:

#### Suggested Changes to Specification

1. **Update Proposed Solution (Data Model & Splitting Algorithm) to resolve E1, E4, and P1:**
   ```diff
    ### Splitting Algorithm
    
    ```python
    def _split_headings(self, blocks: list[Block]) -> list[Block]:
        """Split ATX headings out of unmarked TextBlocks as separate heading blocks."""
        result: list[Block] = []
   -    heading_re = re.compile(r'^(\s*#{1,6}\s)')
   +    heading_re = re.compile(r'^([ ]{0,3}#{1,6}\s)')
    
        for block in blocks:
            if not isinstance(block, TextBlock) or block.marker is not None:
                result.append(block)
                continue
    
            lines = block.content.splitlines(keepends=True)
            base_offset = block.source_offset
            accumulator: list[str] = []
   -        acc_offset = base_offset
   +        current_offset = base_offset
   +        acc_offset = base_offset
            in_code_block = False
    
            for line in lines:
                stripped = line.lstrip()
    
                # Track fenced code block state
                if stripped.startswith('```'):
                    in_code_block = not in_code_block
   +                if not accumulator and current_offset is not None:
   +                    acc_offset = current_offset
                    accumulator.append(line)
   +                if current_offset is not None:
   +                    current_offset += len(line)
                    continue
    
                if in_code_block:
   +                if not accumulator and current_offset is not None:
   +                    acc_offset = current_offset
                    accumulator.append(line)
   +                if current_offset is not None:
   +                    current_offset += len(line)
                    continue
    
                if heading_re.match(line):
                    # Flush preceding text
                    if accumulator:
                        text = ''.join(accumulator)
   -                    if text.strip():
   -                        result.append(TextBlock(content=text, source_offset=acc_offset))
   +                    result.append(TextBlock(content=text, source_offset=acc_offset))
                        accumulator = []
    
                    # Emit heading block
   -                heading_offset = (base_offset + sum(len(l) for l in lines[:lines.index(line)])) if base_offset is not None else None
   -                result.append(TextBlock(content=line, marker='HEADING', source_offset=heading_offset))
   -                acc_offset = (heading_offset + len(line)) if heading_offset is not None else None
   +                result.append(TextBlock(content=line, marker='HEADING', source_offset=current_offset))
   +                if current_offset is not None:
   +                    current_offset += len(line)
   +                acc_offset = current_offset
                else:
   -                if not accumulator and base_offset is not None:
   -                    acc_offset = base_offset + sum(len(l) for l in lines[:lines.index(line)])
   +                if not accumulator and current_offset is not None:
   +                    acc_offset = current_offset
                    accumulator.append(line)
   +                if current_offset is not None:
   +                    current_offset += len(line)
    
            # Flush remaining text
            if accumulator:
                text = ''.join(accumulator)
   -            if text.strip():
   -                result.append(TextBlock(content=text, source_offset=acc_offset))
   +            result.append(TextBlock(content=text, source_offset=acc_offset))
    
        return result
    ```
   ```

2. **Add integration requirements for Edit Markers (E2) and Publishing (E3) under Task 1 & Task 4:**
   ```diff
    ### Task 1: Implement `_split_headings` in `MarkdownExtractor`
    
    **Objective:** Add a method that iterates unmarked `TextBlock`s and splits ATX headings into separate blocks with `marker="HEADING"`.
    
    **Implementation guidance:**
    - File: `src/syntagmax/extractors/markdown.py`
    - Add `_split_headings(self, blocks: list[Block]) -> list[Block]` method.
    ...
   + - Ensure empty/whitespace text blocks are preserved (do not strip or drop them) to retain formatting.
   +
   + **Edit Markers and Publishing Integration:**
   + - File: `src/syntagmax/edit_markers.py`, method `renumber_markers`:
   +   Update the block filter check to ignore blocks whose marker is not in `record.markers` (e.g., `if block.marker is None or block.marker not in record.markers: continue`).
   + - File: `src/syntagmax/publish.py`, method `render_block`:
   +   At the start of `render_block`, if `block.marker == "HEADING"`, set `marker = None` to ensure headings respect the `include_plain_text` publish option.
   ```
