# Spec Critique: Change Summary Report Mode — Implementation Specification

## Executive Summary

This report evaluates the proposed specification for [change-summary-report.spec.md](../specs/change-summary-report.spec.md) under the Product Lens and the Engineering Lens.

The specification introduces a clear, decoupled approach to generate a compact summary of changes (files, artefacts, and text fragments) between two Git revisions. By isolating the rendering logic into a separate `render_summary_report` function, the spec maintains clean separation of concerns. However, there are a couple of critical product gaps and architectural issues that should be addressed before implementation:

1. **Output Filename Collision**: Since the output filename is identical to the full report, running the command with the `--summary` flag will overwrite the full change report (and vice versa) if generated in the same directory.
2. **Hidden Extraction Errors**: The spec explicitly omits extraction errors from the summary. Completely hiding extraction failures could mislead users into believing a file has no changes, when in fact it failed to parse.
3. **Data Model Redundancy**: Reconstructing an `artifact_file_map` in the CLI and passing it via `ChangeReportData` duplicates path tracking that is already resolved during the diff phase.

With these updates applied, the specification will be solid and ready to proceed.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **P1** | Product | 🎯 **Must-Address** | Edge Cases & UX | Running `--summary` overwrites the full report file due to identical output filename formatting. | Append `-summary` to the filename (e.g. `...-summary.md`) when `--summary` is active. |
| **P2** | Product | 🎯 **Must-Address** | Edge Cases & UX | Omitting extraction errors completely hides critical parsing failures from the user, leading to false confidence. | List files with extraction errors under a distinct header or with status "Error" showing only the error message (no fallback diff). |
| **P3** | Product | 💡 **Recommendation** | Edge Cases & UX | Renamed files show status "Renamed" but omit original path details. | Display original path for renames, e.g. `Status: Renamed (from old/path.md)`. |
| **P4** | Product | 💡 **Recommendation** | Edge Cases & UX | No explicit behavior is defined for the empty/no changes state. | Render a fallback "No changes detected." message if there are no differences to display. |
| **E1** | Engineering | 💡 **Recommendation** | Architecture | Reconstructing a parallel `artifact_file_map` in `ChangeReportData` is redundant and splits change metadata. | Add a `file_path: str` field directly to the `ArtifactChange` dataclass. |
| **E2** | Engineering | 💡 **Recommendation** | Code Quality | Discrepancy between Task 1 (no single-line check) and Task 4 (expects single-line formatting). | Explicitly state in Task 1 that `_format_line_range` should format single lines without the `–` separator. |
| **E3** | Engineering | 💡 **Recommendation** | Performance | CLI.py traverses all base/target blocks to reconstruct the artifact file map, which is redundant. | Derive and set the `file_path` directly in `compare_artifacts()` where the blocks and paths are already matched. |
| **E4** | Engineering | 💡 **Recommendation** | Compliance | Reference docs task mentions general `docs/reference/` folder instead of naming the specific `CLI.md` file. | Explicitly target `docs/reference/CLI.md` in Task 6. |

---

## Product Lens Findings

### Edge Cases & UX
* **P1: Output Filename Collision (Severity: 🎯 Must-Address)**
  * *Finding:* The spec specifies that the output filename convention is unchanged. The current filename is `{safe_name}-{base_label}-to-{target_label}-{date_str}.md`. If a user runs both `change report` and `change report --summary` in their workflow, the summary report will overwrite the full report.
  * *Suggestion:* Modify the output filename for summary reports to append `-summary`, e.g., `{safe_name}-{base_label}-to-{target_label}-{date_str}-summary.md`.

* **P2: Hiding Extraction Errors (Severity: 🎯 Must-Address)**
  * *Finding:* Task 4 states that extraction errors are omitted from the summary. Hiding parsing failures entirely is dangerous: if an extractor fails due to syntax errors or bad configuration, the user will see a clean summary showing no changes, giving a false sense of security.
  * *Suggestion:* Render files with extraction errors in the summary. Display the file path and status "Error", followed by the error message, but omit the verbose plain-text fallback diff.

* **P3: Display of Renamed File Origins (Severity: 💡 Recommendation)**
  * *Finding:* For renamed files, the spec requires displaying `Status: Renamed`, but does not mention showing the original file path. The original path is critical context for understanding file moves.
  * *Suggestion:* Include the old file path in the status line, e.g., `Status: Renamed (from old/path.md)`.

* **P4: Handling of Empty Changes State (Severity: 💡 Recommendation)**
  * *Finding:* If base and target revisions are identical, or no files or objects changed, the spec does not define what output should be rendered in summary mode.
  * *Suggestion:* If `file_diffs` is empty or there are no object/text changes, render a clear `No changes detected.` message under the "Changed Files" section.

---

## Engineering Lens Findings

### Architecture Soundness
* **E1: Redundant Global Mapping in `ChangeReportData` (Severity: 💡 Recommendation)**
  * *Finding:* Task 2 adds an `artifact_file_map` dict to `ChangeReportData` to associate artifact IDs with their target file paths. This introduces a parallel mapping structure alongside `ArtifactDiff` and splits the metadata of an artifact change across two separate structures.
  * *Suggestion:* Add `file_path: str` directly to the `ArtifactChange` dataclass. This keeps all metadata associated with a modified artifact in one place.

### Performance & Scalability
* **E3: Redundant Traversal for Path Derivation (Severity: 💡 Recommendation)**
  * *Finding:* Constructing the `artifact_file_map` in `cli.py` requires walking all base and target blocks again. However, `compare_artifacts()` in `change_diff.py` already builds internal maps of `aid -> (block, file_path)` and is the ideal place to assign the file path to `ArtifactChange`.
  * *Suggestion:* Set the `file_path` on `ArtifactChange` directly inside `compare_artifacts()` during comparison.

### Code Quality
* **E2: Discrepancy in Single-Line Range Formatting (Severity: 💡 Recommendation)**
  * *Finding:* Task 1 implementation steps define `_format_line_range` formatting as `lines {start}–{end}`. However, Task 4 expects a test assertion for single-line ranges `(45, 45) -> lines 45`. Without explicit logic, the implementation would render `lines 45–45`.
  * *Suggestion:* Explicitly specify in Task 1 that `_format_line_range` must check if `start == end` and format it as a single line number.

### Compliance
* **E4: Specificity of CLI Reference Documentation (Severity: 💡 Recommendation)**
  * *Finding:* Task 6 states: "docs/reference/ — If a change-report or CLI reference page exists, add equivalent documentation there." Since `docs/reference/CLI.md` is a critical part of the documentation suite, it should be explicitly listed to guarantee compliance with the `spec-doc-update-rule`.
  * *Suggestion:* Update Task 6 to explicitly target `docs/reference/CLI.md`.

---

## Cross-Lens Insights

* **Error Visibility vs. Payload Size (P2 × E1):** By retaining extraction errors in the summary report but omitting the raw unified fallback diff, we satisfy the product requirement for visibility (P2) while maintaining the engineering goal of a compact, lightweight report structure.
* **Unified Metadata (P3 × E1):** Attaching `file_path` directly to `ArtifactChange` (E1) simplifies the grouping logic and makes it easy to support renamed files showing original paths (P3) since the change object holds the original paths.

---

## Verdict & Action Plan

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

### Specific Edits Suggested

1. **Under Requirements in `docs/specs/change-summary-report.spec.md`:**
   * Replace:
     ```markdown
     - Output filename convention is unchanged (same as full report)
     ```
   * With:
     ```markdown
     - Output filename convention appends `-summary` when `--summary` is active (e.g. `{safe_name}-{base_label}-to-{target_label}-{date_str}-summary.md` or `change-{base_label}-to-{target_label}-{date_str}-summary.md` for consolidated reports).
     ```

2. **Under Design Decisions in `docs/specs/change-summary-report.spec.md`:**
   * Replace:
     ```markdown
     4. **Always include artefacts** — artefact changes are always shown in summary mode. Text fragments are shown only when `--include-non-artifact` is active, consistent with the full report behaviour.
     ```
   * With:
     ```markdown
     4. **Always include artefacts** — artefact changes are always shown in summary mode. Text fragments are shown only when `--include-non-artifact` is active, consistent with the full report behaviour.
     5. **Display extraction errors without diffs** — extraction errors are listed under the files with their status marked as "Error" and the error message displayed, but the large fallback plain-text diff is omitted.
     ```

3. **Under Task 1: Summary Renderer Implementation:**
   * Replace:
     ```markdown
     - Implement `_group_artifacts_by_file(data)`:
       - For `added`: key = `file_path` from the tuple element (index 3).
       - For `removed`: key = `file_path` from the tuple element (index 3).
       - For `modified`: look up the artefact's file path from the source data. Since `ArtifactChange` does not carry `file_path`, derive it from `target_blocks` in `ChangeReportData`. Add an optional `artifact_file_map: dict[str, str]` field to `ChangeReportData` (default empty dict) that maps `aid → file_path`, populated during the diff phase.
     ```
   * With:
     ```markdown
     - Implement `_group_artifacts_by_file(data)`:
       - For `added`: key = `file_path` from the tuple element (index 3).
       - For `removed`: key = `file_path` from the tuple element (index 3).
       - For `modified`: key = `file_path` from the `ArtifactChange.file_path` field.
     ```
   * Replace:
     ```markdown
     - Implement `_format_line_range(change)`:
       - Modified: `Modified (lines {old_start}–{old_end} → {new_start}–{new_end})`
       - Added: `Added (lines {new_start}–{new_end})`
       - Removed: `Removed (lines {old_start}–{old_end})`
     ```
   * With:
     ```markdown
     - Implement `_format_line_range(change)`:
       - If a range is single-line (start == end), format as a single number (e.g. `lines 45` instead of `lines 45–45`).
       - Modified: `Modified (lines {old_range} → {new_range})`
       - Added: `Added (lines {new_range})`
       - Removed: `Removed (lines {old_range})`
     ```
   * Replace:
     ```markdown
     - Render per-file sections: for each `FileDiff` in `data.file_diffs`, emit heading, status, objects list (if any), text fragments list (if `data.text_diff` is not None and has entries for that file).
     ```
   * With:
     ```markdown
     - Render per-file sections: for each `FileDiff` in `data.file_diffs`, emit heading, status (including `Renamed (from {old_path})` for renames), objects list (if any), text fragments list (if `data.text_diff` is not None and has entries for that file).
     - Render extraction errors: if a file has an extraction error, render the path, status as `Error`, and the error message.
     - If no files have changes or errors, render `No changes detected.`.
     ```

4. **Under Task 2: Add `artifact_file_map` to ChangeReportData:**
   * Replace the entire Task 2 section with:
     ```markdown
     ### Task 2: Add `file_path` to ArtifactChange

     **Objective:** Extend the `ArtifactChange` dataclass and `compare_artifacts` diff pipeline to carry the target file path.

     **Implementation:**
     - Add `file_path: str = ""` to `ArtifactChange` in `src/syntagmax/change_diff.py`.
     - In `compare_artifacts` inside `src/syntagmax/change_diff.py`, pass the resolved target file path (`target_path`) when instantiating `ArtifactChange`.
     ```

5. **Under Task 6: Documentation Updates:**
   * Replace:
     ```markdown
     - **docs/reference/** — If a change-report or CLI reference page exists, add equivalent documentation there.
     ```
   * With:
     ```markdown
     - **docs/reference/CLI.md** — Add `--summary` option and summary report usage examples under the `change report` section.
     ```
