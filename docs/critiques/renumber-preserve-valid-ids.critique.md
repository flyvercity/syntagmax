# Specification Critique: Preserve Valid IDs During Renumber

## Executive Summary

The specification [renumber-preserve-valid-ids.spec.md](../specs/renumber-preserve-valid-ids.spec.md) addresses a critical user pain point: preserving valid, schema-conforming IDs during artifact renumbering. 

The core two-pass algorithm and the removal of the `--schema` CLI option (making the metamodel the single source of truth) are solid and clean architectural choices. However, the review has identified two **Must-Address** gaps:
1. **Conditional Schema Evaluation**: The specification incorrectly assumes schemas can be resolved and cached purely "per-type". Since metamodels can define conditional ID schemas, resolution and caching must be done "per-artifact" using `evaluate_condition`.
2. **Duplicate Valid ID Handling**: The algorithm currently marks all valid IDs as "keep" and skips them. If duplicate valid IDs exist in the input, they will be preserved, leaving the project in a duplicate ID state.

Addressing these issues, along with recommendations for adding a `--force` flag and logging statistics, will make the implementation robust and highly valuable.

---

## Product Lens Findings

### 1a. Problem Validation
The problem statement is clear, well-scoped, and directly addresses the core need for stability in curated requirement IDs.

### 1b. User Value Assessment
- **MVP analysis**: The logic successfully skips valid IDs.
- **Missing CLI Capability (Recommendation)**: There is currently no way for a user to force a complete re-sequencing of all IDs (e.g., when they want to clean up gaps and start fresh from 1). Bypassing valid-ID preservation is useful in some workflows.

### 1c. Alternative Approaches
The proposed two-pass model is the standard and cleanest way to implement reservation-based numbering. No simpler alternative exists.

### 1d. Edge Cases & User Experience
- **Duplicate IDs (Must-Address)**: If two different artifacts share the same valid ID (e.g. two items have `REQ-002`), both will be marked as "keep" and skipped. The command will run successfully but leave duplicate IDs in the file, which violates the core metamodel constraint. Instead, subsequent duplicates of a reserved ID should be marked for renumbering.

### 1e. Success Measurement
- **Informative CLI Output (Recommendation)**: The user needs to know how many IDs were preserved vs. renumbered. The CLI should print summary statistics (e.g., "Preserved 12 valid IDs, renumbered 4 IDs").

---

## Engineering Lens Findings

### 2a. Architecture Soundness
- **Conditional Schemas (Must-Address)**: In the metamodel, `id` rules can have conditional rules based on the artifact's other attributes (e.g. `condition: { anchor: 'derive', negated: true }`). The spec specifies caching compiled regexes "per-type" and resolving schema "per-type". This will fail or select the wrong schema for types with conditional rules. The schema resolution must evaluate conditions using `evaluate_condition` per-artifact, and the regex cache must be keyed by `(schema, atype)`.
- **Regex Escaping (Recommendation)**: When compiling the ID schema in `compile_id_schema`, non-macro parts of the schema might contain regex special characters. They must be escaped using `re.escape`.

### 2b. Failure Mode Analysis
- **Number Extraction Robustness (Recommendation)**: `extract_number_from_id` must handle cases where the regex matches but the capture group fails to convert to an integer (e.g. if the capture group matches non-digits, though the regex builder restricts it to `\d`).

### 2c. Security & Privacy Review
No security/privacy boundary risks or compliance issues are introduced.

### 2d. Performance & Scalability
- **Resolution Overhead**: Evaluating conditions per-artifact is fast enough for typical projects, but regex caching by `(schema, atype)` is essential to prevent recompilation overhead.

### 2e. Testing Strategy
The test plan is comprehensive and includes the necessary unit and integration tests.

### 2f. Operational Readiness
No database migrations or deployment risks.

### 2g. Dependencies & Integration Risks
No new third-party dependencies are introduced.

---

## Cross-Lens Insights

Evaluating the intersection of Product and Engineering perspectives highlights that resolving duplicate valid IDs (P2) is both a Product necessity (keeping the data clean) and an Engineering necessity (ensuring the system doesn't generate invalid states). Resolving the conditional schemas (E1) ensures the renumbering behavior aligns perfectly with validation rules defined in `analyse.py`.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| E1 | Engineering | 🎯 **Must-Address** | Architecture Soundness | Metamodels can define conditional ID schemas; resolving/caching strictly "per-type" is incorrect. | Resolve schemas per-artifact using `evaluate_condition`. Key the regex cache by `(schema, atype)`. |
| P2 | Product | 🎯 **Must-Address** | Edge Cases & UX | Duplicate valid IDs are both marked as "keep" and preserved, leaving duplicates in place. | In Pass 1, only mark an ID as KEEP if its extracted number hasn't been reserved yet for that type. Otherwise, mark it for renumbering. |
| P1 | Product | 💡 **Recommendation** | Edge Cases & UX | No option to force renumbering of all artifacts once valid-ID preservation is enabled. | Add a `--force` flag to the `edit renumber` CLI command to bypass valid-ID preservation. |
| P3 | Product | 💡 **Recommendation** | Success Measurement | CLI does not log summary statistics of preserved vs. renumbered IDs. | Log a summary of preserved vs. renumbered counts at the end of the execution. |
| E4 | Engineering | 💡 **Recommendation** | Architecture Soundness | Spec does not explicitly require escaping of non-macro characters in schema compiling. | Explicitly state that literal portions of schemas must be escaped with `re.escape`. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

The specification is in good shape overall, but must be updated to address conditional schema resolution (E1) and duplicate ID handling (P2) before proceeding to implementation.

---

## Offer Remediation

Here are the suggested updates to [renumber-preserve-valid-ids.spec.md](../specs/renumber-preserve-valid-ids.spec.md):

### 1. Requirements section additions:
```diff
 5. If no metamodel schema exists for a type, all artifacts of that type are renumbered (no valid-ID protection possible without a schema to validate against).
 6. The `--schema` CLI option is removed. The metamodel is the single source of truth for ID format (both validation and generation).
+7. A `--force` CLI option is added to the `edit renumber` command. When specified, valid-ID preservation is bypassed and all artifacts are renumbered.
+8. Duplicate valid IDs are resolved by preserving the first occurrence (lowest location) and renumbering subsequent duplicates.
```

### 2. Proposed Solution - Schema Resolution section update:
```diff
-### Schema Resolution (Simplified)
-
-With `--schema` removed, the schema for both validation and generation is resolved as:
-
-1. Metamodel schema (`id is TYPE as SCHEMA`) — if defined.
-2. Default `{atype}-{num:3}` — if no metamodel schema exists.
-
-Template IDs (containing `{num`/`{atype}` literals in the source file) are always treated as invalid and renumbered regardless.
+### Schema Resolution
+
+The schema for both validation and generation is resolved on a per-artifact basis:
+
+1. Metamodel schema — if the metamodel defines `id` rules, evaluate their conditions against the artifact's fields (using `evaluate_condition`). Use the schema from the first matching rule.
+2. Default `{atype}-{num:3}` — if no matching metamodel schema rule exists.
+
+Template IDs (containing `{num}` or `{atype}` literals in the source file) are always treated as invalid and renumbered regardless.
```

### 3. Two-Pass Algorithm section update:
```diff
-Pass 1 — Collect reserved numbers:
-  For each artifact (sorted by location):
-    Resolve metamodel schema for its type
-    If schema exists AND aid is not a template AND aid matches the compiled regex:
-      Extract the numeric portion → add to reserved_numbers[atype]
-      Mark artifact as "keep"
-
-Pass 2 — Assign new IDs:
-  Per-type counter starts at 1
-  For each artifact NOT marked "keep":
-    Resolve schema (metamodel → default)
-    Increment counter, skipping reserved_numbers[atype]
-    Generate new ID
+Pass 1 — Collect reserved numbers:
+  For each artifact (sorted by location):
+    Resolve schema for the artifact (evaluating conditions)
+    If schema exists AND aid is not a template AND aid matches the compiled regex:
+      Extract the numeric portion → num
+      If num not in reserved_numbers[atype]:
+        Add num to reserved_numbers[atype]
+        Mark artifact as "keep"
+      Else:
+        Mark artifact for renumbering (resolves duplicate ID conflict)
+    Else:
+      Mark artifact for renumbering
+
+Pass 2 — Assign new IDs:
+  Per-type counter starts at 1
+  For each artifact NOT marked "keep":
+    Resolve schema for the artifact
+    Increment counter, skipping reserved_numbers[atype]
+    Generate new ID
```

### 4. Task 2: Implement two-pass renumber logic and remove `--schema` update:
```diff
-**Objective:** Refactor `renumber_artifacts` in `src/syntagmax/edit.py` to preserve valid IDs and avoid collisions. Remove the `schema_override` parameter and `--schema` CLI option.
+**Objective:** Refactor `renumber_artifacts` in `src/syntagmax/edit.py` to preserve valid IDs and avoid collisions. Remove the `schema_override` parameter and `--schema` CLI option, and add a `--force` flag.
 
 **Implementation guidance:**
 - Remove `--schema` from `cli_edit.py` (the `@click.option` and the parameter).
+- Add `--force` flag to `cli_edit.py` and pass it as `force_all=False` to `renumber_artifacts()`.
 - Remove `schema_override` parameter from `renumber_artifacts()`.
+- Add `force_all` parameter to `renumber_artifacts()`. If `force_all` is True, bypass Pass 1 entirely (treat all artifacts as marked for renumbering).
 - **Pass 1:** Iterate sorted artifacts. For each, look up the metamodel schema for its type. If no schema exists, mark for renumber. If schema exists, compile it (caching per-type), check `artifact.aid`:
+  - Resolve schema on a per-artifact basis by evaluating the metamodel conditions.
-  - If `aid == UNDEFINED_ID` → mark for renumber.
-  - If `aid` contains `{num` or `{atype}` (template literal) → mark for renumber.
-  - If `aid` matches the compiled schema regex → extract number, add to `reserved_numbers[atype]`, mark as KEEP.
+  - If `aid` matches the compiled schema regex → extract number. If number is not yet in `reserved_numbers[atype]`, add to `reserved_numbers[atype]` and mark as KEEP. Else, mark for renumber (duplicate ID).
   - Otherwise → mark for renumber.
 - **Pass 2:** Maintain `counters: dict[str, int]` starting at 0 per type. For each artifact marked for renumber (in the same sorted order):
-  - Resolve schema: metamodel schema if available, otherwise default `{atype}-{num:3}`.
+  - Resolve schema per-artifact.
   - Increment the type's counter, skipping any value in `reserved_numbers[atype]`.
   - Generate the new ID.
+- Print a summary at the end of the run: "Processed {total} artifacts. Preserved {preserved} valid IDs. Renumbered {renumbered} IDs."
```
