# Change Report Detailed Changes Restructuring

## Problem Statement

The current `## Detailed Changes` section lists artifacts flat (all added → all modified → all removed), then text fragments flat. This produces a long undifferentiated list that is hard to navigate. Additionally, the separate `**Status:**` line under each heading adds visual clutter.

## Requirements

**R1:** Restructure the `## Detailed Changes` heading hierarchy to group by category first, then by file:

```
## Detailed Changes
### Artifacts
#### <filename>
##### {atype} {aid} (Status)
...
### Text fragments
#### <filename>
##### Text fragment (Status)
...
### Binary Artifacts
##### {atype} {aid} (Status)
...
### Extraction Errors
#### <filename>
...
```

**R2:** Within each file, artifacts are listed in natural order (as they appear in the diff data — not re-grouped by status).

**R3:** Status is inlined into the heading: `##### SRS BRUD21-SRS-056 (Modified)` — no separate `**Status:**` line.

**R4:** All existing sub-content (text blockquotes, attribute tables, link changes) is preserved — only the grouping/heading levels change.

**R5:** The summary report (`render_summary_report`) is NOT affected by this change.

## Background

- Rendering lives in `src/syntagmax/change_render.py`, function `_render_detailed_changes()`.
- Helper functions `_render_artifact_added/modified/removed`, `_render_text_fragment`, `_render_binary_artifact_change`, `_render_extraction_error` handle individual items.
- Current helpers emit `####` headings + `**Status:** X` on the next line.
- `_group_artifacts_by_file()` helper already exists for the summary report and can be extended.
- Tests in `test_change_report.py` and `test_change_summary.py` check heading content.

## Tasks

### Task 1: Create artifact grouping helper for detailed rendering

**Objective:** Create a helper that groups all artifact changes by file while preserving full render data and natural order.

**Implementation guidance:**
- Create `_group_artifact_changes_by_file(data: ChangeReportData) -> dict[str, list[tuple[str, Any]]]` returning `file_path → list of ('added'|'modified'|'removed', payload)`.
- Payload: for added/removed it's the `(aid, atype, block, file_path)` tuple; for modified it's the `ArtifactChange`.
- Use `dict` (insertion-order) to maintain file ordering from the diff.

**Test requirements:**
- Unit test verifying correct grouping and ordering.

### Task 2: Adjust artifact render helpers — inline status + shift headings

**Objective:** Modify `_render_artifact_added`, `_render_artifact_modified`, `_render_artifact_removed` to inline status into heading and shift heading levels down one.

**Implementation guidance:**
- `_render_artifact_added`: emit `##### {atype} {aid} (Added)` — remove separate `**Status:** Added` line. Sub-sections `##### Text` → `###### Text`, `##### Attributes` → `###### Attributes`.
- `_render_artifact_removed`: emit `##### {atype} {aid} (Removed)` — remove separate status line. Sub-section `##### Text` → `###### Text`.
- `_render_artifact_modified`: emit `##### {atype} {aid} (Modified)` — remove separate status line. `##### Text` → `###### Text`, `##### Attribute Changes` → `###### Attribute Changes`, `##### Link Changes` → `###### Link Changes`. For `###### Previous`/`###### Current` which would become level 7, use `**Previous**`/`**Current**` bold labels instead.

**Test requirements:**
- Unit tests that verify output format of each helper.

### Task 3: Adjust text fragment and binary render helpers — inline status + shift headings

**Objective:** Same treatment for `_render_text_fragment` and `_render_binary_artifact_change`.

**Implementation guidance:**
- `_render_text_fragment`: emit `##### Text fragment ({status})` — remove separate status line. Sub-sections `##### Previous`/`##### Current` → `###### Previous`/`###### Current`.
- `_render_binary_artifact_change`: emit `##### {atype} {aid} ({status_label})` — remove separate status line. Sub-sections `##### Binary Content`/`##### Attribute Changes` → `###### Binary Content`/`###### Attribute Changes`.
- `_render_extraction_error`: adjust heading to `#### {file_path}` (fits under `### Extraction Errors`). Remove the `###` level it currently uses.

**Test requirements:**
- Unit tests for new heading format.

### Task 4: Rewrite `_render_detailed_changes` with new grouped structure

**Objective:** Implement the new category → file → item hierarchy.

**Implementation guidance:**

```python
def _render_detailed_changes(data: ChangeReportData) -> list[str]:
    lines = ['## Detailed Changes', '']
    has_content = False

    # --- Artifacts section ---
    artifacts_by_file = _group_artifact_changes_by_file(data)
    if artifacts_by_file:
        has_content = True
        lines.extend(['### Artifacts', ''])
        for file_path, changes in artifacts_by_file.items():
            lines.extend([f'#### {file_path}', ''])
            for category, payload in changes:
                if category == 'added':
                    aid, atype, block, fp = payload
                    lines.extend(_render_artifact_added(aid, atype, block, fp))
                elif category == 'modified':
                    lines.extend(_render_artifact_modified(payload))
                else:
                    aid, atype, block, fp = payload
                    lines.extend(_render_artifact_removed(aid, atype, block, fp))

    # --- Text fragments section ---
    if data.text_diff:
        all_text = data.text_diff.added + data.text_diff.modified + data.text_diff.removed
        if all_text:
            has_content = True
            fragments_by_file: dict[str, list] = {}
            for change in all_text:
                fragments_by_file.setdefault(change.file_path, []).append(change)
            lines.extend(['### Text fragments', ''])
            for file_path, fragments in fragments_by_file.items():
                lines.extend([f'#### {file_path}', ''])
                for frag in fragments:
                    lines.extend(_render_text_fragment(frag))

    # --- Binary Artifacts section ---
    if data.binary_diff:
        has_content = True
        lines.extend(['### Binary Artifacts', ''])
        for bc in data.binary_diff:
            lines.extend(_render_binary_artifact_change(bc))

    # --- Extraction Errors section ---
    if data.extraction_errors:
        has_content = True
        lines.extend(['### Extraction Errors', ''])
        for error in data.extraction_errors:
            lines.extend(_render_extraction_error(error))

    if not has_content:
        lines.append('No changes detected.')
        lines.append('')

    return lines
```

**Test requirements:**
- Integration test: full report contains `### Artifacts`, `#### <file>`, `##### REQ REQ-001 (Modified)`.
- Test: artifacts from same file share one `####` heading.
- Test: text fragments grouped under `### Text fragments` → `#### <file>`.

### Task 5: Update existing tests

**Objective:** Fix all tests that assert on heading levels or status format.

**Implementation guidance:**
- `test_change_report.py`:
  - `test_report_contains_all_sections`: add checks for `### Artifacts`.
  - `test_artifact_changes_detected`: update to check `##### REQ REQ-001 (Modified)` instead of `'**Status:** Modified'`.
- `test_change_summary.py`: summary report is separate (`render_summary_report`) and should remain unchanged. Verify no breakage.
- Any helper unit tests that check old heading format need updating.

**Test requirements:**
- All tests pass: `uv run pytest tests/test_change_report.py tests/test_change_summary.py`.

### Task 6: Update documentation

**Objective:** Update README.md and spec docs that reference report structure.

**Implementation guidance:**
- README.md "Example Report Structure" section: update to show new hierarchy.
- `docs/specs/change-report.spec.md`: update section order description.

**Test requirements:** N/A

## Example Output (After)

```markdown
## Detailed Changes

### Artifacts

#### REQ/REQ-001.md

##### REQ REQ-001 (Modified)

###### Text

**Previous**

> The system shall do something.

**Current**

> The system shall do something important.

###### Attribute Changes

| Attribute | Previous | Current |
|-----------|----------|---------|
| status | draft | active |
| priority | high | critical |

#### REQ/REQ-003.md

##### REQ REQ-003 (Added)

###### Text

> The system shall have a new feature.

###### Attributes

| Attribute | Value |
|-----------|-------|
| status | draft |
| priority | low |

#### REQ/REQ-002.md

##### REQ REQ-002 (Removed)

###### Text

> The system shall do something else.

### Text fragments

#### REQ/REQ-001.md

##### Text fragment (Added)

- **New lines:** 50-55

> New paragraph content here.

### Binary Artifacts

##### IMG diagram.png (Modified)

###### Binary Content

| Property | Previous | Current |
|----------|----------|---------|
| SHA-256 | `a1b2c3d4e5f6` | `f6e5d4c3b2a1` |
| Size | 24.5 KB | 31.2 KB |
| Dimensions | 800×600 | 1024×768 |

### Extraction Errors

#### REQ/broken.md

⚠️ **Extraction Error**

YAML parse error at line 5

Fallback plain-text diff:

```diff
--- a/REQ/broken.md
+++ b/REQ/broken.md
```
```
