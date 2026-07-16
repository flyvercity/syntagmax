# [x] Task 6: Markdown Report Renderer

## Objective

Create `src/syntagmax/change_render.py` that generates the full Markdown change report from structured diff data.

## Target File

`src/syntagmax/change_render.py`

## Dependencies

- **Task 3** (provides `FileDiff`, `FileStatus` data model)
- **Task 4** (provides `ArtifactDiff`, `ArtifactChange` data model)
- **Task 5** (provides `TextBlockDiff`, `TextFragmentChange` data model)

Note: This task can be implemented in parallel with Tasks 3-5 by defining the expected input data models upfront and using test fixtures.

## Implementation

### Input Data Model

```python
@dataclass
class ChangeReportData:
    base_revision: str
    target_revision: str
    generated_at: str               # UTC timestamp string
    record_name: str                # Input record name
    file_diffs: list[FileDiff]      # All changed files in this record
    artifact_diff: ArtifactDiff     # Artifact-level changes
    text_diff: TextBlockDiff | None # Text block changes (None if --include-non-artifact not set)
```

### Main Function

```python
def render_change_report(data: ChangeReportData) -> str:
```

Returns a complete Markdown string.

### Report Structure

The output must follow this section order:

```markdown
# Change Report

---

## Repository Information

Base revision: <base>
Target revision: <target>
Generated: <timestamp>

---

## Summary

| Parameter | Value |
|-----------|-------|
| Files changed | N |
| Files added | N |
| Files removed | N |
| Artifacts added | N |
| Artifacts modified | N |
| Artifacts removed | N |
| Text fragments modified | N |

---

## Changed Files

### <filepath>

Status: <status>
Objects changed: N
Text fragments: N

---

## Detailed Changes

### <filepath>

#### <Artifact atype> <aid>

Status: <Modified|Added|Removed>

##### Text

###### Previous
```text
...
```

###### Current
```text
...
```

##### Attribute Changes

| Attribute | Previous | Current |
|-----------|----------|---------|
| ... | ... | ... |

#### Text fragment

Status: <Modified|Added|Removed>
Old lines: X-Y
New lines: X-Y

##### Previous
```text
...
```

##### Current
```text
...
```
```

### Formatting Rules

- **No HTML** — only headings, tables, bulleted lists, fenced code blocks, horizontal rules
- Attribute change tables: only show changed attributes (omit unchanged)
- Text changes: use fenced code blocks with `text` language marker
- Renamed files: show both old and new path
- Added files: show `Status: Added` with full content
- Removed files: show `Status: Removed` with previous content
- Horizontal rules (`---`) between major sections

### Summary Statistics Computation

```python
def compute_summary(data: ChangeReportData) -> dict[str, int]:
```

Counts:
- Files by status (changed = modified + renamed, added, removed)
- Artifacts added/modified/removed from `ArtifactDiff`
- Text fragments modified from `TextBlockDiff` (0 if None)

## Technical Notes

- Use f-strings or string building (no template engine dependency needed for this)
- Heading levels: `#` for report title, `##` for major sections, `###` for files, `####` for artifacts/fragments, `#####`/`######` for sub-details
- Ensure tables have proper alignment separators (`|---|`)
- Empty sections should be omitted (e.g., no "Text fragments" section if `text_diff` is None)
- Long text content in code blocks should not be truncated (full content shown)

## Test Requirements

- Test with a complete `ChangeReportData` fixture → verify output contains all expected sections
- Test with only added artifacts (no modified/removed) → verify correct section rendering
- Test with only text changes → verify text fragment sections render correctly
- Test with renamed file → verify old/new path display
- Test summary statistics computation is accurate
- Test that output contains no HTML tags
- Test that output renders correctly in a standard Markdown viewer (validate table syntax, heading levels, code block closure)

## Test File

`tests/test_change_render.py`
