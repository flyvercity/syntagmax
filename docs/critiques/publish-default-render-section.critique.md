# Specification Critique: Default Render Section in Publish Config

**Target Specification**: [docs/specs/publish-default-render-section.spec.md](docs/specs/publish-default-render-section.spec.md)  
**Date**: 2026-08-08  
**Verdict**: ⚠️ **PROCEED WITH UPDATES**

---

## Executive Summary

The proposed specification introduces `_default_` (for artifact rendering) and `_default_marker_` (for text marker rendering), along with the `_remaining_` pseudo-attribute for dynamic field expansion. This is a valuable addition to `syntagmax` that eliminates configuration boilerplate when multiple artifact types or text markers share identical layout structures.

Overall, the feature design is clean, aligned with existing publishing concepts, and well-structured into implementation tasks. However, the critique identified **two must-address engineering/product issues** regarding field resolution with metamodels and case-sensitivity in attribute exclusion, as well as several recommendations to improve marker usability and schema error handling.

---

## Product Lens Findings

### 1a. Problem Validation
- **Strengths**: Clear user pain point. In large documentation suites with dozens of artifact types, repeating table/text render rules across every type creates heavy maintainability overhead.
- **Findings**: The problem statement is well-targeted.

### 1b. User Value & Schema Design
- **Finding (P1 - Static Marker Alias)**: `_default_marker_` requires a static `alias` (e.g. `alias: "Note"`). If a document contains multiple unmapped markers (e.g. `[TODO]`, `[WARNING]`, `[BUG]`), all of them will render with the static title `"Note"`. This loses the distinct identity of the marker.
- **Suggestion**: Support dynamic placeholder expansion in marker aliases (e.g., `{marker}` or defaulting to `block.marker.title()`) when rendering under `_default_marker_`.

### 1c. Edge Cases & User Experience
- **Finding (P2 - Labeling for `_remaining_` fields)**: `_remaining_` fields ignore explicit aliases. Displaying raw field keys like `customer_id` or `sys_priority` in table rows can look unpolished compared to explicitly mapped attributes.
- **Suggestion**: Format raw field names for `_remaining_` by replacing underscores with spaces and applying title-casing (e.g., `customer_id` -> `Customer Id`) when no metamodel title is available.

---

## Engineering Lens Findings

### 2a. Architecture & Data Resolution
- **Finding (E1 - Missing Metamodel Attributes in `_remaining_` Expansion)**: Task 3 guidance states that `_remaining_` iterates over `artifact.fields.keys()`. However, `artifact.fields` only contains attributes actually present on the artifact instance. When `attribute_presence` is set to `'all'` or `'mandatory'`, metamodel-defined attributes that are missing from the artifact file will be omitted from `_remaining_` rendering.
- **Suggestion**: In Task 3, define field collection to merge `artifact.fields.keys()` with `metamodel.artifact_types[a.atype].attributes.keys()` (if metamodel is available) before filtering explicit and excluded fields.

### 2b. Case Sensitivity & Attribute Exclusion
- **Finding (E2 - Case-Sensitivity Bug in `_remaining_` Exclusion)**: `collect_explicit_attributes()` lowercases explicit attribute names, but `artifact.fields` retains original field name casing (e.g. `Status`). If `_remaining_` checks `k not in explicit` without lowercasing `k`, fields like `Status` will bypass exclusion and render twice (in the explicit section and in `_remaining_`).
- **Suggestion**: Normalize field names to lowercase during `_remaining_` exclusion set comparison, while keeping the original key for value lookup.

### 2c. Multi-Section Interaction
- **Finding (E3 - Ambiguity in Multiple `_remaining_` Directives)**: The spec does not define behavior if `_remaining_` is placed in multiple sections of the same render config (e.g., in both a `TableSection` and a `TextSection`).
- **Suggestion**: Clarify in Design Decisions that `_remaining_` expands in every section where it appears against the initial explicit attribute set, or restrict `_remaining_` to at most one occurrence per render configuration.

### 2d. Schema & Validation
- **Finding (E4 - Misplaced Section Types in `render` Dict)**: `PublishConfig.render` uses `dict[str, list[RenderSection]]`. Placing a `TableSection` under `_default_marker_` passes Pydantic parsing but is silently ignored at render time.
- **Suggestion**: Add a warning log in `render_block()` when a section type incompatible with the block type is encountered under `_default_` / `_default_marker_`.

---

## Cross-Lens Insights

- **X1 (Field Discovery & Preserving UX Integrity)**: Resolving `_remaining_` attributes against both `artifact.fields` and the metamodel ensures that `attribute_presence: all` and `attribute_presence: mandatory` work predictably across mapped and unmapped artifact types.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| E1 | Engineering | 🎯 | Failure Modes | `_remaining_` misses metamodel attributes absent on artifact instance when `attribute_presence` is `'all'` or `'mandatory'` | Merge `artifact.fields` keys with metamodel attributes before filtering |
| E2 | Engineering | 🎯 | Case Sensitivity | `_remaining_` exclusion check fails if `artifact.fields` key casing differs from lowercased explicit list | Normalize keys to lowercase during set exclusion comparison |
| P1 | Product | 💡 | User Experience | Static `alias` in `_default_marker_` masks original marker names (`TODO`, `WARNING`, etc.) | Support `{marker}` placeholder or default to `block.marker` in `alias` |
| P2 | Product | 💡 | User Experience | Raw `_remaining_` field keys (e.g. `sys_owner`) render without title-casing | Format raw field keys into title case for table labels |
| E3 | Engineering | 💡 | Edge Cases | Undefined behavior when `_remaining_` appears in multiple sections | Specify that `_remaining_` evaluates independently against initial explicit set |
| E4 | Engineering | 💡 | Architecture | Incompatible section types under default keys pass parsing but fail silently | Add warning log in `render_block()` for mismatched section types |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

The specification is structurally sound and ready for implementation once items **E1** and **E2** are resolved, along with recommended UX improvements **P1** and **P2**.

---

## Proposed Spec Edits (Remediation)

### 1. Fix E1 and E2 in `_remaining_` Expansion (Design & Task 3)

In [docs/specs/publish-default-render-section.spec.md](docs/specs/publish-default-render-section.spec.md), update **Design Decision 3** and **Task 3 Implementation Guidance**:

```diff
- 3. **`_remaining_` is cross-section** — Fields mentioned in ANY section of the render config for a type are excluded from `_remaining_` expansion, preventing duplicate rendering.
+ 3. **`_remaining_` is cross-section** — Fields mentioned in ANY section of the render config for a type are excluded from `_remaining_` expansion (using case-insensitive comparison), preventing duplicate rendering.
+ 3b. **Metamodel-aware field collection** — Field candidate set for `_remaining_` is collected from `artifact.fields.keys()` AND `metamodel` attribute definitions for that artifact type (when metamodel is available), ensuring `attribute_presence: all` and `mandatory` render missing attributes correctly.

- - When `_remaining_` is encountered in a table section: iterate `artifact.fields` keys (minus excluded set), sorted alphabetically, render each as a table row using field name as label and `get_artifact_field_value()` for value
+ - When `_remaining_` is encountered in a section:
+   1. Build candidate field set from `artifact.fields.keys()` union with metamodel attribute names for `a.atype` (if metamodel present).
+   2. Filter candidate fields: remove any field whose lowercased name is in `collect_explicit_attributes(render_sections)`.
+   3. Sort remaining fields alphabetically.
+   4. Render each field subject to `should_render_attribute()`.
```

### 2. Improve P1 (Marker Alias Flexibility)

In **Requirements** and **Task 2**:

```diff
- 7. `_default_marker_` must use `MarkerRenderSection` schema and requires an explicit `alias`
+ 7. `_default_marker_` uses `MarkerRenderSection` schema; if `alias` contains `{marker}` or is set to `"{marker}"`, it dynamically expands to the block's actual marker name.
```

---

### Action Requested

Would you like me to apply these changes to [docs/specs/publish-default-render-section.spec.md](docs/specs/publish-default-render-section.spec.md)?  
**(all / select / none)**
