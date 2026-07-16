# Specification Critique: Change Report Rendering Fixes

This report challenges the specification defined in [change-report-rendering-fixes.spec.md](../specs/change-report-rendering-fixes.spec.md) through two distinct lenses: **Product** and **Engineering**.

---

## Executive Summary

The proposed specification is a valuable quality-of-life update addressing significant readability issues in the Markdown output of the change report (namely, unwieldy lists for changed files, obscured Markdown format inside detailed code blocks, and broken tables due to multi-line fields). 

However, before proceeding to implementation, several **Must-Address** findings must be resolved. These include over-aggressive escaping of `#` inside blockquotes (which corrupts code comments inside blockquoted sections), architectural risks around violating R4 (Summary Report isolation), missing pipe escaping logic in the proposed `_format_field_value`, and unhandled newlines in list values.

Once the remediations proposed below are applied to the specification, the implementation is ready to proceed.

---

## Product Lens Findings

### 1d. Edge Cases & User Experience
*   **P1: Over-Aggressive Escaping of Headers (`#`) inside Blockquotes (🎯 Must-Address)**
    *   **Finding:** The proposed helper `_blockquote_content` escapes any line starting with `#` with a backslash `\#`. However, if the text contents contain code blocks (e.g. ` ```python `), comments starting with `#` will be escaped to `\#`, corrupting the syntax and visual correctness of the code.
    *   **Suggestion:** Modify the helper to detect when it is inside a markdown code block (i.e. between lines matching `^(\s*)```` `) and avoid escaping `#` for those lines. Alternatively, only escape lines where `#` is followed by whitespace (`# `) outside of code blocks.
*   **P2: Casing Inconsistency for Binary Artifact Statuses (💡 Recommendation)**
    *   **Finding:** When grouping binary artifact changes for the `## Changed Files` table (Task 3), the status strings derived from `BinaryArtifactChange.status` are lowercase (`added`, `removed`, `modified_binary`, `modified_metadata`). This conflicts with standard title-case artifact statuses (`Added`, `Modified`, `Removed`), leading to mismatched formatting like `REQ-003 (Added), IMG-001 (modified_binary)`.
    *   **Suggestion:** Normalize status strings from binary changes to standard title-case labels (e.g. `Added`, `Removed`, `Modified`) when displaying them in the Objects column.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
*   **E1: Summary Report R4 Constraint Violation (🎯 Must-Address)**
    *   **Finding:** Requirement R4 states that `render_summary_report` must be unaffected by these changes. However, Task 3 suggests reusing `_group_artifacts_by_file`. If `_group_artifacts_by_file` is modified to include binary artifact changes, `render_summary_report` (which calls it) will automatically inherit this behavior, violating R4.
    *   **Suggestion:** Create a separate helper `_group_all_artifacts_by_file(data)` for the full report, or add an optional parameter `include_binary: bool = False` to `_group_artifacts_by_file` that defaults to `False`.

### 2d. Performance & Scalability / Table Layout Robustness
*   **E2: Mismatch in Escaping Pipe Characters (`|`) (🎯 Must-Address)**
    *   **Finding:** Task 1 implementation guidance states: "Pipe characters (`|`) in the value should be escaped as `\|` to avoid breaking the table." However, the proposed python code for `_format_field_value` completely omits this replacement logic.
    *   **Suggestion:** Add `.replace('|', '\\|')` to the return path of `_format_field_value`.
*   **E3: List Values with Embedded Newlines Bypass Truncation (🎯 Must-Address)**
    *   **Finding:** In `_format_field_value`, the check for lists returns early: `if isinstance(val, list): return ', '.join(str(v) for v in val)`. If the list contains elements with newlines (e.g., `['line1\nline2', 'another']`), the joined string will contain newlines, bypassing the `'\n' in s` check and breaking the markdown table row.
    *   **Suggestion:** Format/truncate individual elements of the list before joining them, or run the join first and then perform the newline check and truncation.

---

## Cross-Lens Insights

*   **X1: Markdown Cell Formatting Safety (🎯 Must-Address)**
    *   **Convergence:** Both product presentation (rendering a clean, unbroken table) and engineering robustness (preventing layout bugs due to unescaped pipes or embedded newlines in lists) depend on the exact behavior of `_format_field_value`. Addressing E2 and E3 simultaneously ensures that no input data shape can corrupt the markdown layout.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 🎯 | Edge Cases & UX | Escaping `#` inside code blocks corrupts comments | Avoid escaping `#` when inside ` ``` ` blocks. |
| P2 | Product | 💡 | Edge Cases & UX | Lowercase status strings for binary artifacts look inconsistent | Normalize status to title case (`Added`/`Modified`/`Removed`). |
| E1 | Engineering | 🎯 | Architecture Soundness | Modifying `_group_artifacts_by_file` directly affects summary reports, violating R4 | Separate the grouping helpers or add a parameterized flag. |
| E2 | Engineering | 🎯 | Failure Modes | Proposed `_format_field_value` code does not escape pipe characters | Add `.replace('\|', '\\\|')` to string conversion. |
| E3 | Engineering | 🎯 | Failure Modes | List elements containing newlines bypass table truncation | Truncate/format list elements individually before joining. |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

Several Must-Address issues exist in the proposed code snippets and guidelines, but they are easily resolvable.

---

## Proposed Spec Remediation

### Remediation for P1 (Escaping `#` in blockquotes)

In `docs/specs/change-report-rendering-fixes.spec.md`, update the `_blockquote_content` code block:

```python
def _blockquote_content(text: str) -> list[str]:
    \"\"\"Convert text to blockquoted lines with headers escaped.

    - Each line is prefixed with '> '.
    - Lines starting with '#' outside of code blocks are escaped: '# Foo' → '\\# Foo'.
    \"\"\"
    lines = []
    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block
        
        # Only escape headers if we are not in a code block
        if not in_code_block and line.lstrip().startswith('#'):
            idx = len(line) - len(line.lstrip())
            line = line[:idx] + '\\' + line[idx:]
            
        lines.append(f'> {line}')
    return lines
```

### Remediation for E2 and E3 (Truncating and escaping field values)

In `docs/specs/change-report-rendering-fixes.spec.md`, update the `_format_field_value` code block:

```python
def _format_field_value(val) -> str:
    \"\"\"Format a field value for display in a table cell, handling newlines and pipes.\"\"\"
    if val is None:
        return '—'
    
    def _format_single(v) -> str:
        s = str(v)
        if '\\n' in s:
            first_line = next((l for l in s.splitlines() if l.strip()), s.splitlines()[0])
            s = f'{first_line.strip()} …'
        return s.replace('|', '\\|')

    if isinstance(val, list):
        return ', '.join(_format_single(v) for v in val)
    return _format_single(val)
```

### Remediation for E1 and P2 (Grouping and status normalization)

In `docs/specs/change-report-rendering-fixes.spec.md` under **Task 3: Refactor `_render_changed_files` to Table Format**, update the guidance:

```markdown
- Build an artefact-by-file mapping from `data.artifact_diff` and `data.binary_diff`.
- To avoid affecting `render_summary_report` (violating R4), either parameterize `_group_artifacts_by_file` or implement a separate grouping helper for the full report that maps paths to title-cased statuses:
  - Normal artifacts: `'Added'`, `'Removed'`, `'Modified'`.
  - Binary artifacts: Map `added` to `'Added'`, `removed` to `'Removed'`, `modified_binary` and `modified_metadata` to `'Modified'`.
```
