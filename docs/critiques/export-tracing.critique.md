# Critique: Export Artifact Tree as Tracing Tables Specification

## Executive Summary

The **Export Artifact Tree as Tracing Tables** specification proposes a new CLI subcommand `trace` to generate forward (child→parent) and reverse (parent→child) traceability matrices in CSV format. It also integrates with the Syntagmax plugin system to allow custom formatting. This feature is highly valuable for projects that require rigorous requirement verification, standards compliance, and impact analysis.

However, the specification has several critical gaps:
1. **Critical Product Gap (Inner Join by default)**: By filtering out lead artifacts that do not have links of the target type, the generated matrix hides orphans and uncovered requirements. In compliance and verification workflows, identifying what is *unlinked* is just as important as showing what is linked.
2. **Critical Engineering Gap (Pipeline Context)**: The recommendation to use `process('tree', config)` is flawed because the `process` function in `src/syntagmax/main.py` does not return the loaded `ArtifactMap` containing the parent/child links; it only returns a `Report` which discards the underlying artifacts.
3. **Usability Gaps**: Setting up a full plugin just to export a TSV (tab-separated) matrix is a high-overhead requirement that can easily be supported directly via a CLI flag or filename extension auto-detection.

Overall, we recommend proceeding with updates to the specification to address these critical points before implementation.

---

## Product Lens Findings

### 1a. Problem Validation & Scope
* **P1 (🎯 Must-Address): Left Outer Join Default for Completeness Check (Orphans / Uncovered Requirements)**
  * **Finding**: The specification describes the matrix logic as iterating child/parent artifacts and finding matching links of the opposite type. In non-flat mode, it emits one row per (child, parent) pair. However, if a child requirement has zero parents of the specified type, it will be completely excluded from the output. In standards-compliant systems engineering (e.g., DO-178C, ISO 26262), this hides "uncovered" requirements. The primary reason for a traceability matrix is to verify 100% coverage, meaning every requirement *must* be trace-linked. An inner-join matrix is a silent failure.
  * **Suggestion**: Change the matrix generation to use a "left outer join" logic by default. Every lead artifact of the requested type must appear in the matrix. If it has no links to artifacts of the target type, it should still appear in a row with the target ID column left blank (or showing a value like `[NO LINK]`).

### 1b. User Value Assessment
* **P2 (💡 Recommendation): Delimiter Option and Tab-Separated Value (TSV) Example Plugin**
  * **Finding**: While a TSV export plugin is a great, lightweight educational tool to illustrate how the custom plugin hook functions, requiring users to write a plugin just to get basic tab-separated values introduces unnecessary friction for a common format.
  * **Suggestion**: Add a `--delimiter` option directly to the built-in CSV writer. Keep the TSV plugin as the tutorial/example plugin in Task 5, but frame it explicitly as an educational example of how to implement `export_trace` rather than a necessity.

### 1d. Edge Cases & User Experience
* **P3 (💡 Recommendation): Graceful Handling of Missing Attributes**
  * **Finding**: If `--attribute <name>` is requested but some lead artifacts do not have that attribute set (or defined in their fields), the behavior is unspecified.
  * **Suggestion**: Missing or undefined attributes should gracefully render as empty string cells (`""`) in the CSV rather than causing a crash or validation error.

* **P4 (🤔 Question): Broken/Unresolved Links in Matrices**
  * **Finding**: If a child requirement references a parent ID that is missing from the project or has a different artifact type, it is not clear how the matrix builder handles this broken link.
  * **Suggestion**: Clarify that broken links of the target parent type should still be listed in the matrix, but clearly marked as `[UNRESOLVED: <ID>]` to alert the user of inconsistencies in the metamodel or database.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
* **E1 (🎯 Must-Address): Inaccessible Artifact Map in `main.process`**
  * **Finding**: The spec suggests using `process('tree', config)` or equivalent to run the pipeline. However, `process()` in `src/syntagmax/main.py` returns a `Report` object which does not expose the raw `ArtifactMap` (the local `artifacts` variable). The artifacts dictionary is discarded.
  * **Suggestion**: The CLI command should manually run the extraction and building sequence (e.g. `extract()`, `build_artifact_map()`, `populate_pids()`, `build_tree()`) or a new helper function should be exposed in `main.py` (e.g. `load_artifact_tree()`) to return both the errors and the artifact map.

### 2d. Performance & Scalability
* **E2 (💡 Recommendation): Explicit Serialization of Custom Attribute Values**
  * **Finding**: Artifact attribute values can be of arbitrary types (integers, booleans, lists, etc.) in the fields dictionary. A direct string representation `TraceRecord.attributes` must serialize these values.
  * **Suggestion**: In `build_trace_matrix`, explicitly convert all attribute values using `str()` (or serialize lists into semicolon-separated lists) before assigning them to the attributes dict.

### 2f. Operational Readiness
* **E3 (💡 Recommendation): Plugin Discovery and Enabled State Check**
  * **Finding**: If the user specifies `--plugin <name>`, the spec says to lookup the plugin from `config.plugins()`. However, `config.plugins()` only returns *enabled* plugins. If a plugin is configured but disabled, or if it doesn't exist, looking it up will fail silently or raise a generic error.
  * **Suggestion**: If `--plugin <name>` is supplied, check if that name exists in the list of enabled plugins. If not, check if it exists in the configured plugins. Raise a descriptive `FatalError` indicating that the plugin is either not configured, disabled, or failed to load.

* **E4 (💡 Recommendation): Clarification of Sequential Record Numbers**
  * **Finding**: The specification states that record numbering starts at 1, but doesn't clarify whether this is a row index or linked to the lead artifact ID.
  * **Suggestion**: Specify that `record_number` is a 1-based sequential row index incremented for every row emitted in the resulting matrix.

---

## Cross-Lens Insights

* **Outer Join by Default reduces verification friction (P1 x E4)**: Using left outer join by default ensures that `record_number` strictly maps to all lead requirements, making it easy to see exactly how many requirements are under analysis, even if they have no links.
* **Standard Delimiter Support reduces plugin bloat (P2 x E3)**: Native TSV/delimiter support prevents users from having to maintain and load boilerplate local python plugins, simplifying plugin registration and reducing load paths.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **P1** | Product | 🎯 **Must-Address** | Scope / Validation | Inner-join logic excludes requirements without trace links, hiding critical gap/orphan metrics. | Use left outer join by default, showing lead artifacts with empty/missing links as blank or `[NO LINK]`. |
| **E1** | Eng | 🎯 **Must-Address** | Architecture | `main.process()` does not return `ArtifactMap`, making the loaded artifacts discarded and inaccessible to the CLI. | Explicitly load and build the artifact tree in the CLI command, or introduce a pipeline helper returning the map. |
| **P2** | Product | 💡 **Recommendation** | Usability / Scope | Custom TSV export requires a plugin, creating high friction for a simple delimiter change, though TSV is useful as an educational example. | Support a `--delimiter` CLI flag or auto-detect based on extension, keeping TSV plugin as an illustrative example. |
| **P3** | Product | 💡 **Recommendation** | Edge Cases | Missing or undefined attributes on an artifact can cause errors or crash serialization. | Default missing attributes to empty string `""` values. |
| **P4** | Product | 🤔 **Question** | Edge Cases | Representation of unresolved/broken references to missing parent IDs is unspecified. | Clear up whether unresolved parent IDs should be omitted, or marked as `[UNRESOLVED: <ID>]`. |
| **E2** | Eng | 💡 **Recommendation** | Architecture | Non-string attribute values in fields are not serialized before matrix mapping. | Force string serialization of all attributes using `str()`. |
| **E3** | Eng | 💡 **Recommendation** | Reliability | Plugin lookup on disabled or unconfigured plugins results in silent failure or unhelpful errors. | Explicitly validate that `--plugin <name>` is configured and enabled, raising a clear `FatalError` if not. |
| **E4** | Eng | 💡 **Recommendation** | Clarity | Unclear if `record_number` represents the lead requirement count or the output row number. | Document `record_number` as the sequential row count in the output. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

The specification covers the necessary CLI parameters, CSV formatting details, and plugin interface. However, proceeding to implementation requires updating the spec to address the **Must-Address** items: **P1** (ensuring all lead requirements are shown using left outer join logic) and **E1** (correcting the CLI data flow to retrieve the loaded `ArtifactMap`).

---

## Offer Remediation

Here are the suggested edits to update the specification in `docs/specs/export-tracing.spec.md`:

### Suggested Edit 1: Clarify left outer join behavior and delimiter/output options
In **Requirements** (lines 7-19), update:
```diff
- - `--flat` flag to merge multiple linked objects into semicolon-separated values
- - `--plugin <name>` to delegate export to a plugin instead of CSV
- - Default output file: `.syntagmax/reports/trace.csv`, with `--output console` for stdout
- - Plugin hook: `export_trace(matrix, config, params) -> None` — plugin handles output itself
- - Update README.md and docs/technical-summary.md
- - Example plugin for tab-separated format
+ - `--flat` flag to merge multiple linked objects into semicolon-separated values
+ - `--delimiter <char>` to specify CSV column separator (default: `,`, or `\t` if file ends in `.tsv`)
+ - `--plugin <name>` to delegate export to a plugin instead of CSV
+ - Left outer join behavior by default: all artifacts of the lead type (child in forward, parent in reverse) must be listed, even if they have no links (leaving the linked ID column empty).
+ - Default output file: `.syntagmax/reports/trace.csv`, with `--output console` for stdout
+ - Plugin hook: `export_trace(matrix, config, params) -> None` — plugin handles output itself
+ - Update README.md and docs/technical-summary.md
+ - Example plugin for tab-separated format (illustrating custom plugin hook usage)
```

### Suggested Edit 2: Update CLI options list
In **CLI Interface** (lines 70-79), update:
```diff
- - `--output <path>` — output file path (default: `.syntagmax/reports/trace.csv`), use `console` for stdout
- - `-f / --config-file` — path to config file (default: `.syntagmax/config.toml`)
+ - `--delimiter <char>` — column delimiter to use (default: `,` or `\t` if suffix is `.tsv`)
+ - `--output <path>` — output file path (default: `.syntagmax/reports/trace.csv`), use `console` for stdout
+ - `-f / --config-file` — path to config file (default: `.syntagmax/config.toml`)
```

### Suggested Edit 3: Update Forward/Reverse Matrix Logic to left outer join and handle unresolved/missing attributes
In **Forward Matrix Logic** (lines 80-86), update:
```diff
- 1. Iterate all artifacts where `atype == child_type`
- 2. For each child artifact, find its parents where `atype == parent_type` (from `pids` resolved against `ArtifactMap`)
- 3. Without `--flat`: emit one row per (child, parent) pair
- 4. With `--flat`: emit one row per child, joining all parent IDs with `"; "`
+ 1. Iterate all artifacts where `atype == child_type`
+ 2. For each child artifact, find its parents where `atype == parent_type` (from `pids` resolved against `ArtifactMap`)
+ 3. If no matching parents exist, emit one row with the child ID and an empty ParentID.
+ 4. Without `--flat`: emit one row per (child, parent) pair.
+ 5. With `--flat`: emit one row per child, joining all parent IDs with `"; "`. If no parents, the parent column is empty.
+ 6. If any requested attribute in `--attribute` is missing on the artifact, output an empty string. If the attribute value is a non-string, serialize it using `str()`.
```

In **Reverse Matrix Logic** (lines 87-93), update:
```diff
- 1. Iterate all artifacts where `atype == parent_type`
- 2. For each parent artifact, find its children where `atype == child_type` (from `children` set)
- 3. Without `--flat`: emit one row per (parent, child) pair
- 4. With `--flat`: emit one row per parent, joining all child IDs with `"; "`
+ 1. Iterate all artifacts where `atype == parent_type`
+ 2. For each parent artifact, find its children where `atype == child_type` (from `children` set)
+ 3. If no matching children exist, emit one row with the parent ID and an empty ChildID.
+ 4. Without `--flat`: emit one row per (parent, child) pair.
+ 5. With `--flat`: emit one row per parent, joining all child IDs with `"; "`. If no children, the child column is empty.
+ 6. If any requested attribute in `--attribute` is missing on the artifact, output an empty string. If the attribute value is a non-string, serialize it using `str()`.
```

### Suggested Edit 4: Correct CLI data flow to retrieve the ArtifactMap
In **Task 4: CLI `trace` command wiring** (lines 218-225), update:
```diff
- - Load config, run the pipeline up through `tree` step (reuse `process('tree', config)` or equivalent — need artifacts built with parent links)
- - Call `build_trace_matrix(...)` with the resolved artifacts
+ - Load config, run the pipeline up through the `tree` step manually (call `extract`, `build_artifact_map`, `populate_pids`, and `build_tree` to retrieve the active `ArtifactMap` along with errors).
+ - Check for errors; if any fatal errors exist, report them.
+ - Call `build_trace_matrix(...)` with the resolved artifacts.
+ - Ensure parent directory of output file is created (e.g. `output_path.parent.mkdir(parents=True, exist_ok=True)`).
```
