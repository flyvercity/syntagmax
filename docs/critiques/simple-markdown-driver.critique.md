# Critique: Simple Markdown Driver

## Executive Summary

The specification [simple-markdown-driver.spec.md](../specs/simple-markdown-driver.spec.md) outlines a clean, lightweight markdown driver (`simple-markdown`) designed to extract single-file artifacts with flat YAML frontmatter. This addresses a real usability gap, avoiding the complexity of nested Obsidian-style markers.

However, our dual-lens review has identified two critical **Must-Address** findings:
1. **Silent Fallback on Malformed YAML (Product & Engineering):** Falling back to treating the entire file as body text when YAML parsing fails is dangerous because it swallows configuration typos (e.g. `id:: TASK-001`) and pollutes the body content.
2. **Regex Robustness (Engineering):** The proposed frontmatter regex will fail to match files that do not have a trailing newline after the closing `---` line, causing silent parsing failures.

Additionally, several **Recommendations** are proposed to align with the codebase's existing patterns (such as case-insensitive attribute parsing, UTF-8 BOM safety, and filtering out empty/null YAML keys).

With these updates implemented, the specification will serve as a robust blueprint for the implementation phase.

---

## Product Lens Findings

### 1a. Problem Validation & Scope
The problem is clear and valid: Obsidian syntax is too heavy for simple standalone markdown documents like tasks and release notes. The scope of this new extractor is well-targeted.

### 1b. User Value Assessment
The proposed flat YAML mapping offers a significant improvement in developer experience for metadata authoring.

### 1d. Edge Cases & UX (Severity: 🎯 Must-Address)
* **Finding (P1 - Malformed YAML Fallback):** Requirement 6 states that malformed YAML will be treated as `contents` on a "best-effort" basis. Under this design, syntax typos (like a mismatched list bracket or incorrect indentation) will cause the entire frontmatter (including the `---` delimiters) to be silently swallowed and imported as raw text in the body. The user loses their metadata, and their body content is polluted without a clear build failure.
* **Suggestion:** If the file begins with a YAML frontmatter block (starts with `---`), any YAML parsing error should be treated as an extraction failure. The extractor should return an `ErrorBlock` with the parse error message, forcing the user to correct the syntax.

### 1d. Edge Cases & UX (Severity: 💡 Recommendation)
* **Finding (P2 - Nested YAML Handling):** Standard YAML frontmatter is flat, but users may occasionally author nested structures (e.g., `metadata: { version: 1 }`). The spec does not define what to do in this case.
* **Suggestion:** Define the behavior for non-scalar nested attributes. Suggest converting dictionary structures into their string representations (or raising a validation error if nested elements are strictly forbidden by the metamodel).

* **Finding (P3 - Case Insensitivity):** Key attributes like `id` and `atype` are handled case-sensitively in the spec.
* **Suggestion:** Consistent with the existing `SidecarExtractor` implementation in [sidecar.py](../extractors/sidecar.py), the `simple-markdown` extractor should perform case-insensitive key lookups for identity configuration (using a case-insensitive pop helper).

### 1e. Success Measurement (Severity: 🤔 Question)
* **Finding (P4 - Success Criteria):** The specification lists no success or verification metrics.
* **Suggestion:** Add a success criteria section. For example, verify that running the `analyze` command parses 100+ documents within 1 second, and verify that the artifacts are successfully represented in the generated console tree.

---

## Engineering Lens Findings

### 2b. Failure Mode Analysis & Regex Robustness (Severity: 🎯 Must-Address)
* **Finding (E1 - Regex Line Ending Limitations):** Task 1 proposes the regex `^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n(.*)` with `re.DOTALL`. If a file ends exactly on the closing `---` line without a trailing newline, the match will fail completely. The extractor will fall back to treating the entire document as body content.
* **Suggestion:** Make the trailing newline group optional and anchor it to the end of the file. Use:
  `^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n(.*))?$`
  and handle cases where the second group is `None` or empty by defaulting the body content to `""`.

### 2c. Dependencies & Integration (Severity: 💡 Recommendation)
* **Finding (E2 - UTF-8 BOM Handling):** Task 1 specifies reading files with `encoding='utf-8'`. On Windows systems, Markdown files are frequently created with a UTF-8 Byte Order Mark (BOM). The BOM character (`\ufeff`) will prevent the `^---` regex from matching at the beginning of the file.
* **Suggestion:** Open files using `encoding='utf-8-sig'` to automatically detect and strip the BOM if present. This is already standard practice in other parts of the codebase, such as [edit_attrs.py](../edit_attrs.py).

### 2d. Performance & Scalability (Severity: 💡 Recommendation)
* **Finding (E3 - Null Value Handling):** Under the current spec, scalar frontmatter attributes are stored via `builder.add_field(key, str(value))`. If a YAML attribute has no value or is set to `null` (e.g., `status: `), pyyaml parses it as `None`. Calling `str(None)` will store the string `"None"` in the database.
* **Suggestion:** Filter out and skip any frontmatter keys whose values are `None` (null) to allow the attributes to be optional or default.

---

## Cross-Lens Insights

* **X1: Safe YAML Parsing (🎯 Must-Address):** Both the product UX and the engineering system benefit from failing fast on malformed YAML. Producing an `ErrorBlock` rather than raw text pollution ensures system data integrity and immediate feedback for the user.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **P1** | Product | 🎯 | Edge Cases & UX | Silently falling back to plain-text body on malformed YAML is dangerous. | Return an `ErrorBlock` if YAML parsing fails when `---` block is present. |
| **P2** | Product | 💡 | Edge Cases & UX | Nested dictionaries/objects in YAML frontmatter are not handled. | Define behavior for nested YAML (e.g., serialize to string or raise error). |
| **P3** | Product | 💡 | Edge Cases & UX | Core attributes `id` and `atype` are case-sensitive. | Use case-insensitive popping to match `SidecarExtractor` behavior. |
| **P4** | Product | 🤔 | Success | Lack of success metrics or post-launch verification. | Add success criteria (e.g., build times, UI representation). |
| **E1** | Engineering | 🎯 | Failure Modes | Frontmatter regex fails on files without a trailing newline after `---`. | Make trailing newline after final `---` optional using `(?:\r?\n(.*))?$`. |
| **E2** | Engineering | 💡 | Dependencies | No UTF-8 BOM handling when reading markdown files. | Use `encoding='utf-8-sig'` to read files robustly. |
| **E3** | Engineering | 💡 | Architecture | Empty/null values in YAML (e.g., `status: `) get stored as string `"None"`. | Skip keys with `None` values or handle them without storing `"None"`. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

*Critical updates to regex parsing and error handling are required to prevent silent failure states. Proceeding to implementation is recommended once the proposed updates are applied.*

---

## Offer Remediation

### Proposed Edits to `docs/specs/simple-markdown-driver.spec.md`

#### Edit 1: YAML Error Handling & BOM Safety (Requirements)

```diff
-6. If a file has no YAML frontmatter or has malformed YAML, best-effort behavior applies: treat the entire file as `contents`, derive ID from filename, use default atype, log a warning.
+6. If a file has no YAML frontmatter, best-effort behavior applies: treat the entire file as `contents`, derive ID from filename, use default atype. If YAML frontmatter is present but malformed, do not parse as best-effort; return an ErrorBlock containing the parsing exception.
```

#### Edit 2: Regex & Parser Logic (Task 1)

```diff
 - Private method `_parse_frontmatter(text: str) -> tuple[dict | None, str]`:
-  - Use regex `^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n(.*)` with `re.DOTALL`
-  - If match: `yaml.safe_load(group(1))` → dict, body = group(2)
-  - If no match or yaml error: return `(None, full_text)`
-  - If yaml result is not a dict: return `(None, full_text)` and log warning
+  - Use regex `^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n(.*))?$` with `re.DOTALL`
+  - If match:
+    - Try to run `yaml.safe_load(group(1))`
+    - If a `yaml.YAMLError` is raised, raise it to the caller so it can construct an `ErrorBlock`
+    - If the result is not a dict, log a warning and treat it as no frontmatter
+    - Return the dict and the body (defaulting to empty string if group(2) is None)
+  - If no match: return `(None, text)`
```

```diff
 - `extract_blocks_from_file(filepath: Path) -> list[Block]`:
-  - Read file with `encoding='utf-8'`
+  - Read file with `encoding='utf-8-sig'` to handle Windows UTF-8 BOM
```

#### Edit 3: Case-Insensitivity & Null Filtering (Task 1)

```diff
-  - Determine `aid`: frontmatter `id` (pop from dict) or `filepath.stem`
-  - Determine `atype`: frontmatter `atype` (pop from dict) or `self._record.default_atype`
+  - Determine `aid` and `atype` using case-insensitive lookup (pop `id` and `atype` case-insensitively, e.g., using `_pop_case_insensitive` helper from sidecar extractor)
```

```diff
-  - Iterate remaining frontmatter keys: for lists call `add_field` per element, for scalars call `add_field` with `str(value)`
+  - Iterate remaining frontmatter keys: skip keys where the value is `None`. For lists call `add_field` per element, for other scalars call `add_field` with `str(value)`
```
