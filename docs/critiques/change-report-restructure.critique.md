# Specification Critique: Change Report Detailed Changes Restructuring

This critique evaluates [change-report-restructure.spec.md](../specs/change-report-restructure.spec.md) through the Product Lens (CEO/Product Lead perspective) and Engineering Lens (Staff Engineer perspective) to identify gaps, risks, and areas for improvement before implementation.

---

## Executive Summary

The specification presents a clear, well-scoped plan to restructure the Detailed Changes section in change reports by grouping items by file under each major category (Artifacts, Text fragments). Inlining the status into the headings removes visual clutter and reduces report length.

The plan is highly viable and well-structured, but it requires key updates to ensure **visual consistency**, **correct Markdown hierarchy**, and **robust code types/imports**. Specifically:
1. **Binary Artifacts** should be grouped by file to match the rest of the report and fix a Markdown heading level violation (skipping H4).
2. Type signatures in the helper function must import required typing modules (`Any`) to avoid runtime `NameError` exceptions.
3. The documentation update task should explicitly cover verification of the reference manual (`CLI.md`).

With these updates addressed, the implementation can proceed immediately.

---

## Product Lens Findings

### 1d. Edge Cases & User Experience
* **Duplicate headings for Text Fragments**: Text fragments do not have unique IDs. Under the new hierarchy, if a file has multiple added or modified text fragments, they will be listed consecutively under `##### Text fragment (Added)` or `##### Text fragment (Modified)`. While acceptable since text fragments are typically few, this could look repetitive. However, since the text content is blockquoted immediately below, it remains readable.
* **Inconsistent representation of Binary Changes**: Binary changes are currently listed flat under `### Binary Artifacts` without file grouping, whereas regular artifacts and text fragments are grouped under `#### <filename>`. Since binary changes are also associated with file paths, grouping them by file makes the report structure more consistent and predictable for the user.

---

## Engineering Lens Findings

### 2a. Architecture Soundness & Markdown Hierarchy
* **Heading Level Progression Violation (H3 -> H5)**: The spec proposes that under `### Binary Artifacts` (H3), each binary change is rendered as `##### {atype} {aid} ({status_label})` (H5). This skips the H4 level, violating sequential heading progression and causing rendering/accessibility issues in some Markdown parsers.
  * *Solution*: Group binary artifacts by file path under `#### {file_path}` (H4), matching the style of the other sections.

### 2b. Code Quality & Typing
* **Missing Typing Imports**: In Task 1 implementation guidance, the signature for `_group_artifact_changes_by_file` uses `Any` (i.e. `dict[str, list[tuple[str, Any]]]`). However, [change_render.py](../../src/syntagmax/change_render.py) does not currently import `Any` from `typing`. Implementing this exactly as described will trigger a runtime `NameError`.
  * *Solution*: Add `from typing import Any` to the imports of `change_render.py` or avoid the use of `Any` in type signatures if not required.

### 2f. Operational Readiness
* **Reference Documentation Coverage**: The spec's Task 6 specifies updating `README.md` and the specification itself, but does not explicitly verify reference files in `docs/reference/` (specifically `CLI.md`). This violates the project factoid `spec-doc-update-rule`.
  * *Solution*: Add a check to verify that no sections in `docs/reference/CLI.md` or other reference pages are broken by the restructured output format.

---

## Cross-Lens Insights

### X1: Grouping Binary Artifacts by File
* **Product Aspect**: Grouping binary artifacts under `#### {file_path}` H4 headings aligns them with the structural presentation of `### Artifacts` and `### Text fragments`, making reports much easier to scan.
* **Engineering Aspect**: It resolves the H3 -> H5 Markdown heading level violation by introducing a clean H4 `#### {file_path}` container level, ensuring strict sequential heading nesting (H3 -> H4 -> H5 -> H6).

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| X1 | Both | 🎯 | Scope & Consistency | Binary artifacts are not grouped by file, causing visual inconsistency and an H3 -> H5 heading skip. | Group binary artifacts by file path using `#### {file_path}` headings, and shift binary changes to H5. |
| E1 | Engineering | 🎯 | Architecture Soundness | `_group_artifact_changes_by_file` type signature uses `Any` which is not imported in [change_render.py](../../src/syntagmax/change_render.py). | Ensure `from typing import Any` is added to imports in [change_render.py](../../src/syntagmax/change_render.py). |
| E2 | Engineering | 💡 | Operational Readiness | Task 6 does not explicitly mention reviewing reference documentation, violating `spec-doc-update-rule`. | Add a verification step to Task 6 for reference files under `docs/reference/`. |
| P1 | Product | 💡 | Edge Cases & UX | Multiple text fragments in the same file will generate duplicate `##### Text fragment` headings. | Retain as is due to the lack of unique fragment IDs, but verify readability during E2E verification. |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

---

## Offer Remediation

Here are the specific suggested updates to [change-report-restructure.spec.md](../specs/change-report-restructure.spec.md):

### Proposed Spec Modification

```diff
-**R1:** Restructure the `## Detailed Changes` heading hierarchy to group by category first, then by file:
-
-```
-## Detailed Changes
-### Artifacts
-#### <filename>
-##### {atype} {aid} (Status)
-...
-### Text fragments
-#### <filename>
-##### Text fragment (Status)
-...
-### Binary Artifacts
-##### {atype} {aid} (Status)
-...
-### Extraction Errors
-#### <filename>
-...
-```
+**R1:** Restructure the `## Detailed Changes` heading hierarchy to group by category first, then by file:
+
+```
+## Detailed Changes
+### Artifacts
+#### <filename>
+##### {atype} {aid} (Status)
+...
+### Text fragments
+#### <filename>
+##### Text fragment (Status)
+...
+### Binary Artifacts
+#### <filename>
+##### {atype} {aid} (Status)
+...
+### Extraction Errors
+#### <filename>
+...
+```
```

```diff
-### Task 1: Create artifact grouping helper for detailed rendering
-
-**Objective:** Create a helper that groups all artifact changes by file while preserving full render data and natural order.
-
-**Implementation guidance:**
-- Create `_group_artifact_changes_by_file(data: ChangeReportData) -> dict[str, list[tuple[str, Any]]]` returning `file_path → list of ('added'|'modified'|'removed', payload)`.
-- Payload: for added/removed it's the `(aid, atype, block, file_path)` tuple; for modified it's the `ArtifactChange`.
-- Use `dict` (insertion-order) to maintain file ordering from the diff.
+### Task 1: Create artifact grouping helper for detailed rendering
+
+**Objective:** Create a helper that groups all artifact changes by file while preserving full render data and natural order.
+
+**Implementation guidance:**
+- Import `Any` from `typing` in [change_render.py](../../src/syntagmax/change_render.py).
+- Create `_group_artifact_changes_by_file(data: ChangeReportData) -> dict[str, list[tuple[str, Any]]]` returning `file_path → list of ('added'|'modified'|'removed', payload)`.
+- Payload: for added/removed it's the `(aid, atype, block, file_path)` tuple; for modified it's the `ArtifactChange`.
+- Use `dict` (insertion-order) to maintain file ordering from the diff.
```

```diff
-### Task 4: Rewrite `_render_detailed_changes` with new grouped structure
-
-**Objective:** Implement the new category → file → item hierarchy.
-
-**Implementation guidance:**
-
-```python
-def _render_detailed_changes(data: ChangeReportData) -> list[str]:
-    lines = ['## Detailed Changes', '']
-    has_content = False
-
-    # --- Artifacts section ---
-    artifacts_by_file = _group_artifact_changes_by_file(data)
-    if artifacts_by_file:
-        has_content = True
-        lines.extend(['### Artifacts', ''])
-        for file_path, changes in artifacts_by_file.items():
-            lines.extend([f'#### {file_path}', ''])
-            for category, payload in changes:
-                if category == 'added':
-                    aid, atype, block, fp = payload
-                    lines.extend(_render_artifact_added(aid, atype, block, fp))
-                elif category == 'modified':
-                    lines.extend(_render_artifact_modified(payload))
-                else:
-                    aid, atype, block, fp = payload
-                    lines.extend(_render_artifact_removed(aid, atype, block, fp))
-
-    # --- Text fragments section ---
-    if data.text_diff:
-        all_text = data.text_diff.added + data.text_diff.modified + data.text_diff.removed
-        if all_text:
-            has_content = True
-            fragments_by_file: dict[str, list] = {}
-            for change in all_text:
-                fragments_by_file.setdefault(change.file_path, []).append(change)
-            lines.extend(['### Text fragments', ''])
-            for file_path, fragments in fragments_by_file.items():
-                lines.extend([f'#### {file_path}', ''])
-                for frag in fragments:
-                    lines.extend(_render_text_fragment(frag))
-
-    # --- Binary Artifacts section ---
-    if data.binary_diff:
-        has_content = True
-        lines.extend(['### Binary Artifacts', ''])
-        for bc in data.binary_diff:
-            lines.extend(_render_binary_artifact_change(bc))
-
-    # --- Extraction Errors section ---
-    if data.extraction_errors:
-        has_content = True
-        lines.extend(['### Extraction Errors', ''])
-        for error in data.extraction_errors:
-            lines.extend(_render_extraction_error(error))
-
-    if not has_content:
-        lines.append('No changes detected.')
-        lines.append('')
-
-    return lines
-```
+### Task 4: Rewrite `_render_detailed_changes` with new grouped structure
+
+**Objective:** Implement the new category → file → item hierarchy.
+
+**Implementation guidance:**
+
+```python
+def _render_detailed_changes(data: ChangeReportData) -> list[str]:
+    lines = ['## Detailed Changes', '']
+    has_content = False
+
+    # --- Artifacts section ---
+    artifacts_by_file = _group_artifact_changes_by_file(data)
+    if artifacts_by_file:
+        has_content = True
+        lines.extend(['### Artifacts', ''])
+        for file_path, changes in artifacts_by_file.items():
+            lines.extend([f'#### {file_path}', ''])
+            for category, payload in changes:
+                if category == 'added':
+                    aid, atype, block, fp = payload
+                    lines.extend(_render_artifact_added(aid, atype, block, fp))
+                elif category == 'modified':
+                    lines.extend(_render_artifact_modified(payload))
+                else:
+                    aid, atype, block, fp = payload
+                    lines.extend(_render_artifact_removed(aid, atype, block, fp))
+
+    # --- Text fragments section ---
+    if data.text_diff:
+        all_text = data.text_diff.added + data.text_diff.modified + data.text_diff.removed
+        if all_text:
+            has_content = True
+            fragments_by_file: dict[str, list] = {}
+            for change in all_text:
+                fragments_by_file.setdefault(change.file_path, []).append(change)
+            lines.extend(['### Text fragments', ''])
+            for file_path, fragments in fragments_by_file.items():
+                lines.extend([f'#### {file_path}', ''])
+                for frag in fragments:
+                    lines.extend(_render_text_fragment(frag))
+
+    # --- Binary Artifacts section ---
+    if data.binary_diff:
+        has_content = True
+        lines.extend(['### Binary Artifacts', ''])
+        binary_by_file = {}
+        for bc in data.binary_diff:
+            binary_by_file.setdefault(bc.file_path, []).append(bc)
+        for file_path, changes in binary_by_file.items():
+            lines.extend([f'#### {file_path}', ''])
+            for bc in changes:
+                lines.extend(_render_binary_artifact_change(bc))
+
+    # --- Extraction Errors section ---
+    if data.extraction_errors:
+        has_content = True
+        lines.extend(['### Extraction Errors', ''])
+        for error in data.extraction_errors:
+            lines.extend(_render_extraction_error(error))
+
+    if not has_content:
+        lines.append('No changes detected.')
+        lines.append('')
+
+    return lines
+```
```

```diff
-### Task 6: Update documentation
-
-**Objective:** Update README.md and spec docs that reference report structure.
-
-**Implementation guidance:**
-- README.md "Example Report Structure" section: update to show new hierarchy.
-- `docs/specs/change-report.spec.md`: update section order description.
+### Task 6: Update documentation
+
+**Objective:** Update README.md and spec docs that reference report structure.
+
+**Implementation guidance:**
+- README.md "Example Report Structure" section: update to show new hierarchy.
+- `docs/specs/change-report.spec.md`: update section order description.
+- Verify and update reference documentation pages (such as `docs/reference/CLI.md`) to align with the new change report format if needed.
```

---

Would you like me to apply these changes? (all / select / none)
