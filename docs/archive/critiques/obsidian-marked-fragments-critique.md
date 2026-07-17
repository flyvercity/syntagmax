# Critique: Obsidian Marked Fragments Spec

## Executive Summary

The **Obsidian Marked Fragments** specification addresses a clear product requirement: allowing users to annotate non-requirement text blocks in Obsidian notes (such as comments, internal notes, or draft content) and extract them with metadata for downstream use (specifically publication filtering).

However, the current spec has one critical product/security gap and one critical engineering validation gap:
1. **Critical Product/Security Gap**: Since publication filtering is deferred to "later," the current `publish` command will strip the marker tags but print the content of marked fragments (e.g., internal private comments) inline as if they were normal public text. This constitutes a silent information leak.
2. **Critical Engineering Gap**: There is no validation on marker name formats (e.g., spaces, special regex characters) or uniqueness, which could cause runtime crashes or regex compilation errors when building the extractor.

Overall, the feature is highly valuable, but we recommend proceeding with targeted updates to the spec to resolve these must-address items before implementation.

---

## Product Lens Findings

### Edge Cases & User Experience
* **P1 (🎯 Must-Address): Publish Command Output Leakage**
  * **Finding**: The spec notes that fragments "are extracted as TextBlocks with a marker field, to be used later for publication filtering." Because filtering is not yet implemented, the current `render_block_tree` in `publish.py` will render these text blocks. However, since the tags are stripped, internal comments like `[COM]Confidential draft note[/COM]` will be rendered in plaintext as `Confidential draft note` with no visual indication that they were comments. This leads to silent leakage of draft/comment text in published documents.
  * **Suggestion**: Modify the spec to define how the `publish` command handles marked fragments. The default behavior should be to *exclude* marked fragments from the published output, or wrap them in Markdown comments (e.g. `<!-- COM: ... -->`) or custom blockquotes so they are not treated as regular body text.
* **P2 (💡 Recommendation): Case Preservation & Canonicalization**
  * **Finding**: The spec specifies that markers are case-insensitive (e.g. `[com]` matches `[COM]`), but does not specify the case of the `marker` field stored on the `TextBlock`.
  * **Suggestion**: Specify that `TextBlock.marker` stores the marker name in its canonical uppercase format (or exactly as declared in the config `markers` list) to avoid downstream consumers needing to perform case-insensitive checks.
* **P3 (💡 Recommendation): Code Block/Span Escaping**
  * **Finding**: Because the extraction processes text blocks between requirements using regex post-processing, any occurrence of `[COM]...[/COM]` inside code blocks (e.g. ` ```python ` blocks) or code spans (e.g. `` `[COM]...` ``) will be parsed and stripped, corrupting the code blocks.
  * **Suggestion**: Document this limitation in the spec, or add a lightweight check to avoid matching markers that are within Markdown code blocks or backtick-enclosed spans.

---

## Engineering Lens Findings

### Architecture Soundness
* **E1 (🎯 Must-Address): Marker Name Validation & Formatting**
  * **Finding**: The spec mandates that fragment markers must not collide with the artifact marker. However, it does not validate the format of the markers themselves. If a user defines a marker with spaces (e.g. `"CO M"`) or regex-active characters (e.g. `"COM+"`, `"C[O]M"`), it can break the regex compilation or parser behavior. It also doesn't prevent duplicate markers in the `markers` list.
  * **Suggestion**: Require that marker names:
    1. Must match the regex `^[a-zA-Z0-9_-]+$` (alphanumeric, hyphens, and underscores only).
    2. Must be non-empty and unique (case-insensitively) within the `markers` list.
    3. Are escaped using `re.escape()` before being interpolated into any regex.

### Dependencies & Integration Risks
* **E2 (💡 Recommendation): Driver Scope Validation**
  * **Finding**: The spec states: "Obsidian driver only in this version". However, `ObsidianExtractor` inherits directly from `MarkdownExtractor`. If a user adds `markers` to a standard `markdown` driver input source, it may implicitly run or behave unexpectedly.
  * **Suggestion**: Add a configuration validation rule in `Config._read_input_records()`: if `markers` is specified on an input record whose `driver` is not `"obsidian"`, raise a `FatalError` explaining that fragment markers are only supported on the `obsidian` driver.

### Performance & Scalability
* **E3 (💡 Recommendation): Splitting Algorithm Definition**
  * **Finding**: The spec suggests post-processing the block list and splitting `TextBlock`s. A naive implementation (e.g., repeatedly regex-replacing each marker one by one) could result in quadratic complexity, incorrect split ordering, or issues with overlapping tags.
  * **Suggestion**: Specify a single-pass extraction algorithm using a unified regex:
    `re.compile(rf'\[({escaped_markers})\](.*?)\[/\1\]', re.IGNORECASE | re.DOTALL)`
    where `escaped_markers` is `|`.join of escaped configured markers. This processes the text linearly and handles multiple different markers correctly in a single pass.

---

## Cross-Lens Insights

### Product Simplification × Engineering Risk Reduction
* **Addressing Publish Leakage (P1)**: By implementing a simple default behavior in `publish` (e.g., ignoring/filtering out any `TextBlock` where `marker is not None`), we completely eliminate the product risk of leaking confidential comments, and we also avoid having to design a complex filtering engine in this version. The implementation remains extremely simple (just a conditional check in `render_block_tree`).

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **P1** | Product | 🎯 **Must-Address** | Edge Cases / UX | Marked fragments (e.g. `COM`) are stripped of tags but printed inline in `publish`, leaking sensitive comments. | Have the `publish` command omit marked `TextBlock`s by default, or wrap them in Markdown comments. |
| **E1** | Eng | 🎯 **Must-Address** | Architecture | No validation on marker name format or uniqueness, leading to regex crash/parsing risks. | Enforce `^[a-zA-Z0-9_-]+$` format, uniqueness, and use `re.escape()` when building regexes. |
| **P2** | Product | 💡 **Recommendation** | Edge Cases / UX | Stored `marker` case behavior is undefined. | Store the canonical uppercase version of the marker in `TextBlock.marker`. |
| **P3** | Product | 💡 **Recommendation** | Edge Cases / UX | Markers inside code blocks or inline code spans will be parsed/stripped. | Document this limitation or skip text within backticks/code blocks. |
| **E2** | Eng | 💡 **Recommendation** | Integration Risks | `markers` config might be accepted on non-obsidian drivers despite the "obsidian only" requirement. | Validate that `markers` is only configured when `driver = "obsidian"`. |
| **E3** | Eng | 💡 **Recommendation** | Performance | Naive splitting algorithm could be slow or buggy for multiple markers. | Define a single-pass regex compilation pattern using all configured markers. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

The specification is solid in its core goals, but the two **Must-Address** items (P1: publish leakage, E1: marker validation) should be resolved before starting the implementation.

---

## Offer Remediation

Here are the proposed edits to update the specification in `docs/specs/obsidian-marked-fragments.md`:

### Suggested Edit 1: Update Requirements with Validation and Publish behavior
In **Requirements** (line 7-15), add validation details and define `publish` behavior:
```diff
 ## Requirements
 
 - Markers are configured via a `markers` list on the input record (config level)
 - Markers are case-insensitive
+- Marker names must be non-empty, unique, and follow the pattern `^[a-zA-Z0-9_-]+$`
 - No nesting or overlap between fragment markers
 - Fragment markers must not collide with the artifact marker — collision is a fatal config error
+- Fragment markers are only allowed when the driver is `"obsidian"`
 - `TextBlock` gains a `marker: str | None` field (`None` = regular unmarked text)
 - Obsidian driver only in this version
+- Stored `marker` values in `TextBlock` will be canonicalized to uppercase
+- The `publish` command (in `render_block_tree`) will by default exclude marked `TextBlock`s from the rendered markdown output to prevent leakage of comments/notes.
```

### Suggested Edit 2: Update Task Breakdown
In **Task 2: Add markers to config model and InputRecord, with collision validation** (line 70-79), add the new validations:
```diff
 ### Task 2: Add `markers` to config model and `InputRecord`, with collision validation
 
 - **Objective:** Allow `markers = ["COM", "NOTE"]` in TOML input config; validate no collision with artifact marker.
 - **Implementation:**
   - Add `markers: list[str] = Field(default_factory=list)` to `InputConfig`
   - Add `markers: list[str]` to `InputRecord` dataclass
   - In `Config._read_input_records()`, pass markers through and validate:
+    - If `markers` is non-empty and `driver` is not `"obsidian"`, raise `FatalError`
+    - If any marker is empty or contains non-alphanumeric/hyphen/underscore characters, raise `FatalError`
+    - If there are duplicate markers (case-insensitive) in the list, raise `FatalError`
     - If any marker (case-insensitive) equals the artifact marker, raise `FatalError`
 - **Test:** Unit test that a config with colliding markers raises `FatalError`; config with valid markers loads successfully.
 - **Demo:** Loading a config with `markers = ["COM"]` and `marker = "REQ"` succeeds; loading with `markers = ["REQ"]` and `marker = "REQ"` fails fatally.
```

In **Task 3: Implement fragment splitting in MarkdownExtractor** (line 80-91), detail the splitting algorithm and case canonicalization:
```diff
 ### Task 3: Implement fragment splitting in MarkdownExtractor
 
 - **Objective:** After artifact extraction, split inter-artifact text by configured fragment markers into marked and unmarked `TextBlock`s.
 - **Implementation:**
   - In `_extract_blocks_from_markdown()`, after the main loop produces the `blocks` list, add a post-processing step:
-    - For each `TextBlock` in the list, scan its `content` for `[MARKER]...[/MARKER]` patterns (case-insensitive) using the configured `self._record.markers`
-    - Split into a sequence of `TextBlock(content=..., marker=None)` and `TextBlock(content=..., marker='COM')` etc.
+    - If `self._record.markers` is empty, skip post-processing.
+    - Otherwise, build a single regex: `re.compile(rf'\[({escaped_markers})\](.*?)\[/\1\]', re.IGNORECASE | re.DOTALL)` where `escaped_markers` is the pipe-joined escaped marker names.
+    - For each `TextBlock` in the list, find all matches. Split the content into unmarked text segments and marked segments.
+    - For marked segments, set `marker` to the matched marker name, canonicalized to uppercase.
     - Replace the original `TextBlock` with the split sequence
   - This keeps the artifact extraction logic untouched and cleanly separates concerns.
 - **Test:** Unit test with markdown containing `[COM]comment[/COM]` between artifacts; verify the block list contains marked `TextBlock`s with correct marker values and content.
 - **Demo:** Extracting from a file with `[COM]...[/COM]` produces `TextBlock(content='comment', marker='COM')` in the block list.
```

In **Task 5: Amend the obsidian example to showcase the capability** (line 106-114), or add a new task for updating `publish`:
Add **Task 7: Update publish rendering behavior**:
```markdown
### Task 7: Exclude marked fragments from publish output

- **Objective:** Prevent leakage of comments/notes in published documents.
- **Implementation:** In `render_block_tree` in `src/syntagmax/publish.py`, when iterating over blocks:
  - If `isinstance(block, TextBlock)` and `block.marker is not None`, omit it from `parts` (or format as a Markdown comment if configured/preferred).
- **Test:** Run publish on the updated example and verify `[COM]` and `[NOTE]` fragments do not appear in the generated output.
```
