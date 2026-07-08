# Spec Critique: Preserve YAML Attribute Order in Editing Commands

## Executive Summary

This report evaluates the proposed specification for [preserve-yaml-attr-order.md](../specs/preserve-yaml-attr-order.md) under the Product Lens and the Engineering Lens.

The specification addresses a critical developer pain point: preventing noisy git diffs and comment loss when editing requirements. The technical approach of using `ruamel.yaml` for round-trip parsing is correct and standard. However, several critical gaps and areas for improvement have been identified:
1. **Graceful Error Handling**: The spec does not define how to handle syntactically malformed YAML blocks, which would result in raw Python tracebacks/crashes in the CLI.
2. **Line Ending Integrity**: Windows environments using CRLF line endings run the risk of introducing mixed line endings (LF inside the YAML block, CRLF in the rest of the file) if not explicitly handled.
3. **API Redundancy**: The proposed utility module defines three helper functions with restrictive type signatures. Consolidating this to a single unified function reduces complexity and simplifies the implementation.
4. **Missing/Empty `attrs:` Block Handling**: The logic for initializing or updating the `attrs:` block when it is missing or empty is not fully specified.

With these updates applied, the specification is highly recommended to proceed to implementation.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 🎯 | Edge Cases & UX | Malformed YAML blocks in files will cause `ruamel.yaml` parser crashes, bubble up, and exit the CLI with a traceback. | Catch `YAMLError` during parsing and output a clear, user-friendly message with the filename and artifact ID. |
| E1 | Engineering | 🎯 | Failure Mode Analysis | Parsing and re-emitting YAML on Windows platforms can lead to mixed line endings (LF inside YAML block, CRLF in the file). | Ensure output YAML newlines are normalized to the file's detected line endings. |
| P2 | Product | 💡 | Edge Cases & UX | The helper API defines redundant functions (`roundtrip_set_attr`, `roundtrip_del_attr`, `roundtrip_dump`) with overly restrictive type signatures. | Consolidate the API to a single `roundtrip_modify_attrs` function that supports `Any` values for flexibility. |
| E2 | Engineering | 💡 | Architecture Soundness | Spec does not detail behavior when a YAML block is present but does not contain an `attrs:` key (or `attrs:` is null). | Specify that `yaml_utils` must handle missing `attrs` keys by initializing them as empty mapping objects. |
| E3 | Engineering | 💡 | Architecture Soundness | In-memory `MarkdownArtifact.yaml_data` (based on `benedict`) is not synchronized with the written file during/after editing. | Document this design choice: since the CLI command runs and terminates, updating the written file is sufficient, but in-memory sync is skipped. |

---

## Product Lens Findings

### Edge Cases & User Experience

* **P1: Malformed YAML Error Handling (Severity: 🎯 Must-Address)**
  * *Finding:* If a user-provided Markdown file has a syntax error in a YAML block, the `ruamel.yaml` parser will raise an exception (such as `ParserError` or `ScannerError`). Without explicit try-except logic, the CLI tool will crash and display a long traceback to the developer, which is poor UX.
  * *Suggestion:* Catch `YAMLError` during parsing. Print a clean, actionable error message (e.g. "Error parsing YAML block in artifact <AID> in <file>: <details>") and exit gracefully.

* **P2: Redundant Helper API & Restrictive Type Hints (Severity: 💡 Recommendation)**
  * *Finding:* The task breakdown specifies three different helper functions (`roundtrip_set_attr`, `roundtrip_del_attr`, `roundtrip_dump`) and restricts attribute values to `str | list`. In practice, requirements attributes can be booleans, integers, floats, or custom objects. Furthermore, a single general-purpose function `roundtrip_modify_attrs(raw_yaml: str, attrs_delta: dict[str, Any], operation: str) -> str` can easily handle all cases for both `edit attrs` and `edit renumber` (by passing `{'id': new_id}` and `operation='replace'`).
  * *Suggestion:* Simplify the spec to define a single unified function in `yaml_utils.py`:
    ```python
    def roundtrip_modify_attrs(
        raw_yaml: str,
        attrs_delta: dict[str, Any],
        operation: str,
    ) -> str:
        """Apply a batch of attribute updates (add, del, replace) to raw YAML attrs."""
    ```

---

## Engineering Lens Findings

### Failure Mode Analysis

* **E1: Line Ending (CRLF vs LF) Preservation (Severity: 🎯 Must-Address)**
  * *Finding:* On Windows systems, files frequently use CRLF (`\r\n`) line endings. If the modified YAML returned by `ruamel.yaml` uses LF (`\n`) and is injected directly into a segment, git will flag mixed line endings, or the entire block could show as modified.
  * *Suggestion:* Ensure the helper functions (or the caller in `markdown.py`) replace `\n` in the serialized output with the detected `newline` characters of the source file.

### Architecture Soundness

* **E2: Missing/Null `attrs:` Key (Severity: 💡 Recommendation)**
  * *Finding:* If a requirement block has a YAML section but does not contain an `attrs:` key (e.g. only contains `title: Example`), attempts to modify attributes under `attrs:` will fail or crash unless `attrs:` is initialized first.
  * *Suggestion:* Spec should explicitly state that the YAML modifier must check if the `attrs` key exists. If it does not exist, or is set to null, it must be initialized to an empty mapping (such as `CommentedMap`) before applying the updates.

* **E3: In-memory Artifact Synchronization (Severity: 💡 Recommendation)**
  * *Finding:* The proposed solution operates directly on raw YAML text and avoids changing `MarkdownArtifact.yaml_data` (which is typed as `benedict`). This prevents a large refactor, but means the in-memory representation becomes stale once written to disk.
  * *Suggestion:* This is a sound trade-off because the CLI executes a single command and exits. However, it should be explicitly documented in a code comment to prevent future developers from assuming the in-memory `MarkdownArtifact` objects are kept in sync during the write process.

---

## Cross-Lens Insights

* **API Consolidation (P2 × E2):**
  Consolidating the three proposed helper functions into a single `roundtrip_modify_attrs` function reduces code duplication, making it much easier to write comprehensive tests and apply uniform error handling (P1) and line ending preservation (E1).

---

## Verdict & Action Plan

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

### Specific Edits Suggested

1. **Under Task 1: Add `ruamel.yaml` dependency and create `yaml_utils.py` helper module:**
   * Replace:
     ```markdown
     - Create `src/syntagmax/yaml_utils.py` with:
       - `roundtrip_set_attr(raw_yaml: str, attr_name: str, attr_value: str | list) -> str` — set/add a key under `attrs:`
       - `roundtrip_del_attr(raw_yaml: str, attr_name: str) -> str` — delete a key under `attrs:`
       - `roundtrip_dump(raw_yaml: str, modifications: dict[str, str | None | list]) -> str` — apply a batch of add/del/replace to the `attrs:` section
     ```
   * With:
     ```markdown
     - Create `src/syntagmax/yaml_utils.py` with a single unified utility function:
       - `roundtrip_modify_attrs(raw_yaml: str, attrs_delta: dict[str, Any], operation: str) -> str`
     - Inside `roundtrip_modify_attrs`:
       - Parse `raw_yaml` using `ruamel.yaml.YAML(typ='rt')`.
       - Catch `ruamel.yaml.error.YAMLError` and raise a custom exception (e.g., `YAMLParsingError`) to allow callers to report clear errors.
       - Verify if the `attrs` key is present; if missing or null, initialize it to an empty `CommentedMap`.
       - Apply changes to `attrs` based on `operation` (`add`, `del`, `replace`):
         - `add`: Insert key/value if not already present.
         - `del`: Remove key if present.
         - `replace`: Set key/value if value is not None, else remove it.
       - Serialize the output back to a string, ensuring line endings match the format of the file.
     ```

2. **Under Task 2: Refactor `_update_yaml_attrs` to use round-trip editing:**
   * Replace:
     ```markdown
     - Apply modifications using `yaml_utils.roundtrip_dump()`
     ```
   * With:
     ```markdown
     - Apply modifications using `yaml_utils.roundtrip_modify_attrs(raw_yaml, attrs_delta, operation)`
     - Catch `YAMLParsingError`, log a user-friendly error with the artifact's ID and filename, and exit.
     ```

3. **Under Task 3: Refactor `update_artifacts` (renumber) to use round-trip editing:**
   * Replace:
     ```markdown
     - Use `yaml_utils.roundtrip_set_attr(raw_yaml, 'id', new_id)` to update only the `id` key
     ```
   * With:
     ```markdown
     - Use `yaml_utils.roundtrip_modify_attrs(raw_yaml, {'id': new_id}, 'replace')` to update only the `id` key
     - Catch `YAMLParsingError`, log a user-friendly error, and exit.
     ```
