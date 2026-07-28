# Specification Critique: Preserve Valid IDs During Renumber (v2)

## Executive Summary

The specification [renumber-preserve-valid-ids.spec.md](../specs/renumber-preserve-valid-ids.spec.md) outlines the transition of the `edit renumber` command to a non-destructive, reservation-based algorithm that preserves existing, valid IDs while resolving new IDs sequentially.

This review confirms that the two-pass algorithm and the removal of the `--schema` CLI option in favor of metamodel-defined schemas are excellent, robust design decisions. However, a deep review of the spec and the codebase has revealed a key gap:
1. **Duplicate Valid ID Handling (Warning)**: If duplicate valid IDs exist, they should both be preserved (as resolving duplicate IDs is another command's responsibility), but a warning listing the duplicates should be displayed to the user at the end of execution.
2. **Clarification on conditional schemas (Misconception resolved)**: The previous critique draft suggested that ID rules could be conditional. A check of `metamodel.lark` and `metamodel.py` confirms that the grammar does not support conditions on `id` rules. Therefore, the specification's assumption that ID schema resolution is strictly per-type is **correct**.

Overall, the specification is near-complete. With the resolutions suggested in this critique, the feature is ready to proceed to implementation.

---

## Product Lens Findings

### 1a. Problem Validation
- The problem is well-defined: preventing the unnecessary churn of requirements IDs when they are already conforming to the schema is a critical developer-experience and consistency feature.

### 1b. User Value Assessment
- The addition of `--force` and the automatic fallback to `{atype}-{num:3}` are highly valuable UX improvements.
- **UX Warning on Duplicate IDs (Recommendation)**: If the codebase has duplicate valid IDs (e.g., two different artifacts have `REQ-002`), both should be preserved (as resolving duplicates is another command's responsibility). However, the command should detect these duplicates and print a warning listing them at the end of execution to notify the user.

### 1c. Alternative Approaches
- The two-pass approach is standard and necessary. No simpler or cleaner approach achieves the desired behavior.

### 1d. Edge Cases & User Experience
- The padding semantics (`{num:3}` matching 3 or more digits) are intuitive and prevent accidental ID clipping (e.g. `REQ-1000` is kept valid).

### 1e. Success Measurement
- The end summary (preserved, renumbered, total) is a good success metric for the run.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
- **Single Regex validation/extraction (Recommendation)**: Specifying that `compile_id_schema` includes a capture group around the `{num}` macro (e.g., `(\d{N,})` or `(\d+)`) allows `extract_number_from_id` to perform validation and number extraction in a single regex match check, simplifying implementation.
- **Confirming Per-Type Schema Resolution**: A review of `metamodel.lark` confirms that `id` rules do not support `[condition]` blocks, which means schemas are indeed resolved strictly per-type. The spec's architecture is sound here.

### 2b. Failure Mode Analysis
- **Zero-macro schemas (Recommendation)**: If a schema has 0 `{num}` macros (e.g. `id is string as "REQ-FIXED"`), the specification does not declare this an error, but it is impossible to renumber using it. Metamodel validation and the renumber command should require exactly one `{num}` macro in a schema, rather than "at most one".

### 2c. Security & Privacy Review
- No security or privacy boundary concerns were identified.

### 2d. Performance & Scalability
- The proposed regex and type-counter caching strategies are sufficient to prevent performance bottlenecks.

### 2e. Testing Strategy
- The test plans outlined in Task 1, 2, and 3 are detailed and cover all major paths.

### 2f. Operational Readiness
- Standard CalVer versioning and ruff checks are planned.

### 2g. Dependencies & Integration Risks
- **Integration with analyse.py (Recommendation)**: The new helper `compile_id_schema` changes regex matching behavior from exact length to minimum padding (Requirement 7). The validation in `analyse.py` must import and use this new helper to avoid discrepancy.

---

## Cross-Lens Insights

Warning the user about duplicate IDs (P1) is critical for the user to be aware of data integrity issues. Unifying schema validation and extraction using a single capture group (E1) simplifies code maintenance and ensures validation consistency.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 💡 **Recommendation** | Edge Cases & UX | Duplicate valid IDs are preserved without warning. | Track `seen_valid_ids` in Pass 1 and print a warning listing duplicate IDs at the end of the command execution. |
| E1 | Engineering | 💡 **Recommendation** | Architecture Soundness | Spec suggests `compile_id_schema` and `extract_number_from_id` are separate steps. | Define `compile_id_schema` to compile with a capture group around the `{num}` macro. This enables both validation and extraction in a single match. |
| E2 | Engineering | 💡 **Recommendation** | Failure Modes | Schemas with 0 `{num}` macros are allowed but cannot support sequential ID generation. | Require exactly one `{num}` macro in the metamodel schema / template ID. Fail loading/execution if 0 are found. |
| E3 | Engineering | 💡 **Recommendation** | Integration Risks | `analyse.py`'s current exact-padding check will diverge from the new minimum-padding requirements. | Update `analyse.py` to import and use `compile_id_schema` from `id_utils.py`. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

The specification is highly detailed and structurally sound. Addressing the duplicate ID resolution and schema validation enhancements will make it robust.

---

## Offer Remediation

Here are the suggested updates to [renumber-preserve-valid-ids.spec.md](../specs/renumber-preserve-valid-ids.spec.md):

### 1. Requirements section updates:
```diff
-14. Any schema may contain at most one `{num}` macro. Multiple `{num}` macros in a metamodel schema must cause metamodel loading to fail. Multiple `{num}` macros detected in an artifact's template ID must cause the renumber command to fail before making any changes.
+14. Any schema must contain exactly one `{num}` macro to be valid for renumbering. Zero or multiple `{num}` macros in a metamodel schema must cause metamodel loading to fail. Zero or multiple `{num}` macros detected in an artifact's template ID must cause the renumber command to fail before making any changes.
-15. `{num:N}` denotes minimum padding, not a strict digit count. `REQ-1234` is valid under schema `REQ-{num:3}`.
+15. `{num:N}` denotes minimum padding, not a strict digit count. `REQ-1234` is valid under schema `REQ-{num:3}`.
+17. Duplicate valid IDs are both preserved (resolving duplicates is another command's responsibility), but a warning listing duplicate IDs is printed at the end of execution.
```

### 2. Two-Pass Algorithm section updates:
```diff
 Pass 1 — Maximum number extraction:
   For each artifact (sorted by location):
     Resolve schema
-    Validate schema has at most one {num} macro (fail if multiple)
-    If artifact's ID matches the compiled schema regex:
-      Extract the numeric portion → update max_number[atype] if larger
+    Validate schema has exactly one {num} macro (fail if 0 or multiple)
+    If artifact's ID matches the compiled schema regex (using a capture group for {num}):
+      Extract the numeric portion → update max_number[atype] if larger
+      If ID in seen_ids:
+        Record duplicate warning for ID
+      Else:
+        Add ID to seen_ids
```

### 3. Task 1 Description updates:
```diff
-**Objective:** Create `compile_id_schema(schema: str, atype: str) -> re.Pattern` and `extract_number_from_id(aid: str, schema: str, atype: str) -> int | None` as reusable helpers in a new `src/syntagmax/id_utils.py` module. Also add `count_num_macros(schema: str) -> int` for validation.
+**Objective:** Create `compile_id_schema(schema: str, atype: str) -> re.Pattern` and `extract_number_from_id(aid: str, schema: str, atype: str) -> int | None` as reusable helpers in a new `src/syntagmax/id_utils.py` module. Also add `count_num_macros(schema: str) -> int` for validation. Update `analyse.py` to use `compile_id_schema`.
 
 **Implementation guidance:**
 - Move `_NUM_PATTERN` to `id_utils.py` as the canonical location.
 - `compile_id_schema` builds a regex by:
   1. Replacing `{atype}` with `re.escape(atype)`.
   2. Splitting the remaining string on `{num}` / `{num:N}` boundaries.
   3. Escaping each literal segment with `re.escape`.
-  4. Replacing `{num:N}` with `\d{N,}` (minimum N digits) and `{num}` with `\d+`.
+  4. Replacing `{num:N}` with a capture group `(\d{N,})` (minimum N digits) and `{num}` with `(\d+)`.
   5. Anchoring with `^...$`.
-- `extract_number_from_id` does the same but uses a capture group `(\d{N,})` or `(\d+)` around the num position, then returns `int(match.group(1))` or `None`.
+- `extract_number_from_id` matches the compiled schema regex against the ID and returns `int(match.group(1))` if matched, else `None`.
 - `count_num_macros(schema: str) -> int` returns the number of `{num}` / `{num:N}` occurrences in a schema string.
-- Update `analyse.py` to import from `id_utils` instead of duplicating the logic.
+- Update `analyse.py` to import `compile_id_schema` from `id_utils` and use it for validating IDs (ensuring alignment on minimum padding logic).
 - Update `edit.py` to import `_NUM_PATTERN` from `id_utils`.
```

### 4. Task 3 Description updates:
```diff
**Objective:** Refactor `renumber_artifacts` in `src/syntagmax/edit.py` to preserve valid IDs and avoid collisions. Remove the `schema_override` parameter and `--schema` CLI option, and add a `--force` flag.

**Implementation guidance:**
- Remove `--schema` from `cli_edit.py`.
- Add `--force` flag to `cli_edit.py` and pass it as `force_all=False` to `renumber_artifacts()`.
- Remove `schema_override` parameter from `renumber_artifacts()`.
- Add `force_all` parameter to `renumber_artifacts()`. If `force_all` is True, bypass Pass 1 entirely.
- **Pass 1:** Iterate sorted artifacts. For each, look up the metamodel schema for its type. If no schema exists, mark for renumber. If schema exists, compile it:
  - If `aid` matches the compiled schema regex → extract number, add to `reserved_numbers[atype]`, and track in `seen_ids`. If it was already in `seen_ids`, record a duplicate warning.
  - Otherwise → mark for renumber.
- **Pass 2:** Maintain `counters: dict[str, int]` starting at 0 per type. For each artifact marked for renumber:
  - Resolve schema per-artifact.
  - Increment the type's counter, skipping any value in `reserved_numbers[atype]`.
  - Generate the new ID.
- Print a summary at the end of the run: "Processed {total} artifacts. Preserved {preserved} valid IDs. Renumbered {renumbered} IDs."
  If duplicates were detected, also print: "Warning: Duplicate valid IDs detected: {list of duplicate IDs}."
```
