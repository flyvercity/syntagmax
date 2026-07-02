# Critique: Publishing Configuration System Specification

## Executive Summary

The **Publishing Configuration System** specification addresses a critical limitation of the current Syntagmax implementation: the hardcoded markdown rendering format of the `publish` command. Enabling declarative, per-record configuration of headings, prefixes, and attribute presentation (tables or text sections) is a major step forward for usability.

However, the specification contains several product and engineering gaps that must be addressed before implementation:
1. **Critical Product Gap (Regression)**: The proposed CLI removes the ability to publish a single, consolidated requirements document. Splitting the output into separate per-record files is a severe regression for users who need unified specification documents.
2. **Critical Product Gap (Git Noise)**: Appending `<YYYY-MM-DD>` to output filenames by default is anti-pattern in a git-based requirements workflow, causing file index churn and breaking relative links across document revisions.
3. **Critical Engineering Gap (Parsing Ambiguity)**: The schema relies on an ambiguous union of `TextSection` and `MarkerRenderSection` under the `render` key, and the `attributes` list uses a list-of-dicts representation that requires explicit single-key validation to prevent undefined ordering or parsing errors.

Overall, we recommend proceeding with updates to the specification to address these critical points.

---

## Product Lens Findings

### 1a. Problem Validation & Scope Gaps
* **P1 (🎯 Must-Address): Regression in Consolidated Publishing (Single File Output)**
  * **Finding**: The current `publish` command compiles all input blocks across all records and outputs them into a single, user-defined markdown file. The proposed CLI changes the command to write individual files named `<INPUT_RECORD_NAME>_<YYYY-MM-DD>.md` in an output directory. This completely eliminates the ability to produce a single, unified specification document (e.g. a master System Specification combining system requirements, hardware requirements, and comments).
  * **Suggestion**: Keep the capability to write a consolidated document. If the user runs `publish` with a target file path (e.g., `syntagmax publish --output report.md`), it should compile all records into that single file. If the user specifies a directory or runs with `--output-dir`, separate files can be written.

* **P2 (🎯 Must-Address): Hardcoded Date Suffix in File Names**
  * **Finding**: Naming files `<INPUT_RECORD_NAME>_<YYYY-MM-DD>.md` by default creates significant git repository noise and breaks cross-file markdown links whenever the publish command is run on a new day. A core philosophy of Syntagmax is git compatibility; git itself tracks historical versions and dates, so suffixing the date in the filename is redundant and detrimental to stable linking.
  * **Suggestion**: Make the output filename stable (e.g. `<INPUT_RECORD_NAME>.md`) by default. Provide an optional `--date-suffix` CLI flag or a configuration option to append the date if specifically requested.

### 1d. Edge Cases & User Experience
* **P3 (💡 Recommendation): Specification of Numeric Prefix Stripping Pattern**
  * **Finding**: The parameter `remove_numeric_prefixes_in_headers` is defined as "Strip numeric prefixes from headings", but the exact pattern is not specified. It is unclear if it strips `1.2.3 Title`, `1 Title`, `1- Title`, or `A.1 Title`.
  * **Suggestion**: Explicitly specify the regex pattern used to identify and strip numeric prefixes. The recommended pattern is `r'^\s*([0-9]+(\.[0-9]+)*\s*[-.]?|[0-9]+\s+)(.*)$'`, which matches leading numbers, dot-separated subnumbers, and optional trailing dashes or dots followed by spaces.

* **P4 (💡 Recommendation): Handle case-insensitive attribute naming**
  * **Finding**: The example `publish.yaml` lists attributes in uppercase (e.g. `RATIO`, `COMMENT`), while standard metamodels and parser outcomes are typically lowercase. Mismatches in casing could lead to empty rendering blocks.
  * **Suggestion**: Specify that the attribute key lookup in the artifact fields dictionary must be case-insensitive.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
* **E1 (🎯 Must-Address): Ambiguity in `render` Dictionary Union Parsing**
  * **Finding**: Under the `render` key, the list of sections can contain `TextSection` or `MarkerRenderSection`. Both models have `type: Literal['text']` and `mode: Literal['block', 'inline']`. They differ because `TextSection` has `attributes` (for artifact rendering) and `MarkerRenderSection` has `alias` directly (for text blocks with markers). Without explicit schemas distinguishing these models, Pydantic's default union matching could mis-classify them.
  * **Suggestion**: Explicitly model the schemas. Define `MarkerRenderSection` as not allowing `attributes` and `TextSection` as requiring `attributes` and not having `alias` at the section level.

* **E2 (🎯 Must-Address): Validation of Attribute List Structures**
  * **Finding**: The `attributes` field is defined as `list[dict[str, AttributeRender]]`. A dictionary can technically contain multiple keys (e.g., `{'id': {'alias': 'ID'}, 'parent': {'alias': 'Parent'}}`). If a user accidentally groups multiple keys in a single list item, it causes undefined rendering order and breaks the schema validation model.
  * **Suggestion**: Enforce via Pydantic `@field_validator` that each dictionary inside the `attributes` list contains exactly one key-value pair.

* **E3 (💡 Recommendation): Define Exact Markdown Spacing and Formatting Rules**
  * **Finding**: The specification does not define how newlines, spacing, or bold/italic markers are structured for `block` and `inline` rendering modes. This makes rendering implementation arbitrary and can result in messy markdown (double blank lines, run-together lines, etc.).
  * **Suggestion**: Specify the exact markdown formatting rules:
    - Bolding: Aliases in both block and inline modes must be enclosed in double asterisks (`**Alias**`).
    - Inline Mode Format: `**Alias**: Value` on a single line.
    - Block Mode Format:
      ```markdown
      **Alias**

      Value
      ```
    - Spacing: Each section (table or text) and each block within a file record must be separated by exactly one blank line.

---

## Cross-Lens Insights

### Product Simplification × Engineering Risk Reduction
* **Consolidated Output Logic (P1 × E3)**: Retaining support for compiling all blocks into a single output file simplifies the publishing logic. If a single file is requested, the renderer compiles all blocks sequentially into one string, bypassing directory checks and complex file writing loops.
* **Predictable Linking (P2 × E1)**: Using stable names by default eliminates the engineering complexity of cleaning up stale, date-stamped markdown files in the project workspace and ensures document linking remains functional.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **P1** | Product | 🎯 **Must-Address** | Scope / UX | Proposed CLI removes consolidated (single-file) publishing capability, forcing separate per-record outputs. | Support direct output to a single file path. If output is a directory, write separate files. |
| **P2** | Product | 🎯 **Must-Address** | Git Integration | Hardcoded date suffix in output filenames causes git noise and breaks cross-document linking. | Use stable filenames (e.g. `<INPUT_RECORD_NAME>.md`) by default. Provide an optional CLI flag/setting for date suffix. |
| **E1** | Eng | 🎯 **Must-Address** | Architecture | Ambiguity between `TextSection` and `MarkerRenderSection` schemas can cause Pydantic parsing errors. | Explicitly model `attributes` and `alias` field constraints to allow distinct discriminated union resolution. |
| **E2** | Eng | 🎯 **Must-Address** | Architecture | `attributes` as `list[dict]` allows dicts with multiple keys, causing undefined ordering. | Add Pydantic validator enforcing exactly one key per dictionary in the list. |
| **P3** | Product | 💡 **Recommendation** | Edge Cases | Definition of numeric prefix stripping is ambiguous. | Define the exact regex pattern used for prefix stripping (e.g. dot-separated numbers). |
| **P4** | Product | 💡 **Recommendation** | UX | Attribute lookup is case-sensitive, risk of mismatching user config casing. | Perform case-insensitive attribute lookup. |
| **E3** | Eng | 💡 **Recommendation** | Architecture | Markdown spacing, bolding, and separator rules are not defined, leading to unpredictable layouts. | Specify exact bolding syntax and require exactly one blank line between sections/blocks. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

The specification is well-motivated and provides a robust structure for configurable requirements publishing. However, the identified **Must-Address** items (P1: consolidated output, P2: stable filenames, E1: union ambiguity, E2: single-key validation) must be incorporated into the spec before implementation begins.

---

## Offer Remediation

Here are the proposed edits to update the specification in [publish-config.spec.md](file:///C:/Users/boris/projects/flyvercity/stmx/syntagmax/docs/specs/publish-config.spec.md):

### Suggested Edit 1: Keep single-file option and remove hardcoded date suffix by default
In **Requirements** (lines 7-18), update the output and CLI description:
```diff
 ## Requirements
 
 - Per-input-record YAML publish config (shared or overridden via `publish` field in `config.toml`)
 - Default file: `.syntagmax/publish.yaml`; falls back to all-default rendering if absent
 - Config controls: `start_level`, `remove_numeric_prefixes_in_headers`, `include_plain_text`, `ignore_plain_text_prefixes`, and `render` section
 - `render` section maps artifact types and markers to rendering rules (table/text sections with attribute aliases)
-- CLI: `syntagmax publish <record-name> [<record-name>...]` or `--all`; `--output <dir>` for output directory
-- Output naming: `<output_dir>/<INPUT_RECORD_NAME>_<YYYY-MM-DD>.md`
+- CLI: `syntagmax publish [RECORDS...] [--all] [--output <path-or-dir>] [-f <config-file>]`
+- Output naming:
+  - If `--output` specifies a file path (or when compiling all to one file): render all records sequentially into that single file.
+  - If `--output` is a directory (or by default): `<output_dir>/<INPUT_RECORD_NAME>.md`.
+  - Date suffix `_<YYYY-MM-DD>` is only appended if an optional `--date-suffix` CLI flag is provided.
 - Fallback rendering for unmapped artifact types (heading + body + metadata table)
 - JSON Schema derived from Pydantic model
 - Update `example/publishing` to match new config format
```

### Suggested Edit 2: Clarify header stripping regex, case-insensitivity, and layout spacing
In **Global Parameters** and **Render Section** (lines 73-138), define specific formatting and parsing rules:
```diff
 ### Global Parameters
 
 | Parameter | Type | Description | Default |
 |-----------|------|-------------|---------|
 | `start_level` | int | Starting heading level in the output document (offset) | 1 |
-| `remove_numeric_prefixes_in_headers` | bool | Strip numeric prefixes from headings | true |
+| `remove_numeric_prefixes_in_headers` | bool | Strip numeric prefixes (matching regex `^\s*([0-9]+(\.[0-9]+)*\s*[-.]?|[0-9]+\s+)(.*)$`) | true |
 | `include_plain_text` | bool | Include plain text (non-requirements) in the output | true |
 | `ignore_plain_text_prefixes` | list[str] | Line prefixes to exclude from the output | [] |
 
 ### Render Section
 
 The `render` section defines rendering parameters for artifact and non-artifact text blocks. Keys correspond to artifact types or block markers.
 
 #### Artifact Render Configuration
 
 Each artifact is rendered as a set of sections. Each section can be either `table` or `text`.
 
 Every section definition shall have an `attributes` definition:
 
 ```yaml
 render:
   <atype>:
     - type: text
       mode: block
       attributes:
         - id:
             alias: "Identifier"
         - parent:
             alias: "Parent"
 ```
 
 - Attribute names (e.g., `id`, `parent`) shall be defined by the metamodel.
+- Attribute lookup in the artifact fields is case-insensitive.
 - `alias` is the name used in publication: for tables — a column name; for text sections — a caption.
 - For text sections: `mode` field (enum: `block`, `inline`) defines whether output appears on a new line after the alias (`block`) or on the same line (`inline`).
 
-**Block mode example:**
-```text
-**Requirement**
-
-The system shall do X.
-```
-
-**Inline mode example:**
-```text
-**Rationale**: Because Y.
-```
+##### Markdown Layout Rules:
+- **Bolding**: Attribute and marker aliases must be wrapped in `**` (e.g. `**Alias**`).
+- **Block Mode**:
+  ```markdown
+  **Alias**
+
+  Value
+  ```
+- **Inline Mode**:
+  `**Alias**: Value` on a single line.
+- **Spacing**: A single blank line must be inserted between adjacent sections and blocks.
```

### Suggested Edit 3: Detail Pydantic Model validation rules
In **Task 1: Define the PublishConfig Pydantic model** (lines 182-194), specify structural validation constraints:
```diff
 ### Task 1: Define the PublishConfig Pydantic model
 
 - Create `src/syntagmax/publish_config.py` with Pydantic models representing the publish YAML schema.
 - Models:
   - `AttributeRender`: `alias: str`
-  - `TableSection`: `type: Literal['table']`, `attributes: list[dict[str, AttributeRender]]`
-  - `TextSection`: `type: Literal['text']`, `mode: Literal['block', 'inline']`, `attributes: list[dict[str, AttributeRender]]` (for artifacts)
-  - `MarkerRenderSection`: `type: Literal['text']`, `mode: Literal['block', 'inline']`, `alias: str` (for markers)
+  - `TableSection`: `type: Literal['table']`, `attributes: list[dict[str, AttributeRender]]` (validator enforces each dict in the list contains exactly one key)
+  - `TextSection`: `type: Literal['text']`, `mode: Literal['block', 'inline']`, `attributes: list[dict[str, AttributeRender]]` (validator enforces each dict contains exactly one key)
+  - `MarkerRenderSection`: `type: Literal['text']`, `mode: Literal['block', 'inline']`, `alias: str` (enforces `attributes` field is absent)
   - `PublishConfig`: `start_level: int = 1`, `remove_numeric_prefixes_in_headers: bool = True`, `include_plain_text: bool = True`, `ignore_plain_text_prefixes: list[str] = []`, `render: dict[str, list[...]]`
 - Add a `load_publish_config(path: Path | None, root_dir: Path) -> PublishConfig` function that loads YAML or returns defaults.
 - Test: Unit tests verifying model validation with valid/invalid YAML inputs, default values, and discriminated union parsing of section types.
```
