# Critique: Fix H1 Heading Level to Respect File Hierarchy in Publish

## Executive Summary

The specification `docs/specs/heading-level-hierarchy.spec.md` outlines a solid plan to fix a critical styling and formatting issue in the publish pipeline: first-level Markdown headings (H1) inside file contents rendering at absolute levels instead of respecting the file's hierarchical position.

This critique has been updated to disregard backward compatibility concerns. Following this update, there are no remaining **Must-Address** blockers. The spec is sound and ready for implementation. We highlight two minor recommendations and one question regarding H6 capping in deeply nested folder structures.

**Verdict**: ⚠️ **PROCEED WITH UPDATES** (No critical blockers found; recommended minor updates only).

---

## Product Lens Findings

### 1a. Problem Validation
- **Status**: Validated.
- **Details**: The problem is well-defined. Users publishing hierarchical structures have to deal with broken Document Outlines/Table of Contents due to absolute H1 headings in nested files.
- **Severity**: None (No issues found).

### 1b. User Value Assessment
- **Status**: Validated.
- **Details**: This feature directly aligns with user expectations for professional, properly nested report output.
- **Severity**: None.

### 1c. Edge Cases & User Experience
- **Finding (P1)**: **Lack of configuration toggle to disable automatic shifting.**
- **Severity**: 💡 **Recommendation**
- **Description**: Automatically shifting headings based on file system depth is highly desirable for consolidated documents. However, for users with flat documents or pre-offset source files, this could be unexpected. The specification doesn't mention whether heading shifting should be toggleable.
- **Suggestion**: Document that heading shifting is the default behavior. In a future iteration, consider adding a configuration key (e.g. `shift_headings_by_path: bool = true`) to the YAML configurations to allow users to bypass this feature.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
- **Finding (E1)**: **Inaccurate count of `pub_config.start_level` usages in `render_block`.**
- **Severity**: 💡 **Recommendation**
- **Description**: Task 1 mentions replacing "all 3 uses of `pub_config.start_level` inside `render_block` with `effective_level`". There are actually **four** occurrences of `pub_config.start_level` inside `render_block` in `src/syntagmax/publish.py`. Missing one would cause inconsistent behavior.
- **Suggestion**: Update Task 1's description to specify replacing all four occurrences of `pub_config.start_level`.

### 2b. Failure Mode Analysis
- **Finding (E2)**: **Deep Path Heading Level Capping UX.**
- **Severity**: 🤔 **Question**
- **Description**: In deeply nested structures (e.g., nesting depth >= 5), directory, file, and H1/H2 content headings will all cap at H6 (`######`). While technically correct due to markdown limitations, the output loses visual distinction.
- **Suggestion**: Clarify if a warning should be emitted to the user during publishing if heading levels exceed H6, or if silent capping is the accepted standard.

---

## Cross-Lens Insights

No major convergence points since backward compatibility concerns have been removed.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| E1 | Engineering | 💡 | Architecture Soundness | Inaccurate count of `pub_config.start_level` usages in `render_block` (4 instead of 3) | Update Task 1 instruction to modify all 4 occurrences |
| P1 | Product | 💡 | Edge Cases & UX | No configuration option to disable automatic heading level shifting | Document default behavior and plan `shift_headings_by_path` config toggle for v2 |
| E2 | Engineering | 🤔 | Failure Modes | Silent capping at H6 for deeply nested directory paths | Determine whether to emit a CLI warning for deep hierarchies |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

No critical blockers remain. Incorporating the recommendations will ensure a smoother implementation and better documentation.

---

## Remediation

### Proposed Specification Edits

#### Update Task 1 (under "Task Breakdown")
```diff
-### Task 1: Add `content_level` parameter to `render_block` and update internal usage
-
-**Objective:** Modify `render_block` to accept an optional `content_level` parameter and use it for all heading adjustments instead of `pub_config.start_level`.
-
-**Implementation guidance:**
-- Change signature: `render_block(block, pub_config, context=None, content_level: int | None = None)`
-- At the top of the function, resolve: `effective_level = content_level if content_level is not None else pub_config.start_level`
-- Replace all 3 uses of `pub_config.start_level` inside `render_block` with `effective_level`
-- Update the `render_artifact_fallback` call: pass `effective_level` instead of `pub_config.start_level`
-- Change `render_artifact_fallback(artifact, start_level)` to `render_artifact_fallback(artifact, content_level)` with internal logic: `level = min(6, content_level)` (remove the `+ 2`)
+### Task 1: Add `content_level` parameter to `render_block` and update internal usage
+
+**Objective:** Modify `render_block` to accept an optional `content_level` parameter and use it for all heading adjustments instead of `pub_config.start_level`.
+
+**Implementation guidance:**
+- Change signature: `render_block(block, pub_config, context=None, content_level: int | None = None)`
+- At the top of the function, resolve: `effective_level = content_level if content_level is not None else pub_config.start_level`
+- Replace all 4 uses of `pub_config.start_level` inside `render_block` with `effective_level`
+- Update the `render_artifact_fallback` call: pass `effective_level` instead of `pub_config.start_level`
+- Change `render_artifact_fallback(artifact, start_level)` to `render_artifact_fallback(artifact, content_level)` with internal logic: `level = min(6, content_level)` (remove the `+ 2`)
```
