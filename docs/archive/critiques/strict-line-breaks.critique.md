# Spec Critique: Strict Line Breaks Setting for Obsidian Driver

## Executive Summary

This report evaluates the proposed specification for [strict-line-breaks.spec.md](../specs/strict-line-breaks.spec.md) under the Product Lens and the Engineering Lens.

The specification introduces a `strict_line_breaks` configuration setting for the Obsidian driver, aiming to match Obsidian's relaxed newline rendering (which treats single newlines as visible breaks) when exporting or publishing content.

While the feature addresses a clear user requirement, three critical implementation and design gaps must be addressed to ensure correctness, compatibility, and robust parsing:
1. **TOML Native Boolean Parsing**: Declaring the field type strictly as `str` in Pydantic will fail when native TOML booleans (`true`/`false`) are supplied by users in their configuration files.
2. **Windows (CRLF) Compatibility**: Applying a naive `\n` substitution on CRLF files will produce malformed line endings (e.g. `\r  \n`), breaking layout rendering and pre-commit lint validation.
3. **Paragraph Breaks Safety**: The proposed regex check fails to protect empty/whitespace-only lines separating paragraphs. This will incorrectly merge separate paragraphs into a single paragraph with hard breaks.
4. **Markdown Block Elements Protection**: The transformation must exclude Markdown block-level constructs (tables, headings, list items, thematic breaks). Appending `  ` to table separator lines or rows breaks Markdown table parsing in Pandoc.

By resolving these issues through a structured, block-element-aware parsing logic that handles CRLF dynamically, the implementation will be clean, robust, and safe.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **P1** | Product | 🎯 **Must-Address** | Configuration | User-provided native TOML booleans (`true`/`false`) will raise Pydantic validation errors if the field is typed strictly as `str`. | Change field type to `str \| bool` and normalize to string in validation. |
| **P2** | Product | 💡 **Recommendation** | Defaults | The proposed default is `"on"` (strict), which is inconsistent with Obsidian's default settings (relaxed breaks). | Document this defaults mismatch clearly and recommend using `"auto"` or `"off"`. |
| **E1** | Engineering | 🎯 **Must-Address** | Compatibility | Naive `\n` replacement on Windows platforms using CRLF line endings results in malformed `\r  \n`. | Process lines individually, stripping and restoring line endings (`\r\n` vs `\n`) dynamically. |
| **E2** | Engineering | 🎯 **Must-Address** | Correctness | Space-filled empty lines (`\n   \n`) are not recognized as paragraph boundaries, causing separate paragraphs to merge. | Preserve empty/whitespace-only lines and skip adding hard breaks to lines preceding them. |
| **E3** | Engineering | 💡 **Recommendation** | Layout | Blindly appending spaces to table rows, lists, headings, and thematic breaks corrupts Markdown syntax and breaks Pandoc. | Exclude block-level lines (headings, table rows, lists, thematic breaks) from transformation. |

---

## Product Lens Findings

### Configuration Validation
* **P1: Native TOML Boolean Parsing (Severity: 🎯 Must-Address)**
  * *Finding:* TOML files support native boolean values (e.g., `strict_line_breaks = false`). If the Pydantic field is typed strictly as `str`, it will raise a validation error on start when native booleans are used.
  * *Suggestion:* Declare the field as `strict_line_breaks: str | bool = Field(default="on")` in `config.py` and convert booleans to strings (e.g. `True` -> `"true"`, `False` -> `"false"`) in the `@field_validator`.

### Configuration Defaults
* **P2: Default Mismatch with Obsidian (Severity: 💡 Recommendation)**
  * *Finding:* Obsidian defaults to relaxed breaks (`strictLineBreaks: false` / OFF). Syntagmax proposes defaulting `strict_line_breaks` to `"on"`. Users expecting a seamless match with default Obsidian behavior might be confused.
  * *Suggestion:* Document this difference clearly in configuration references and the README, advising users to use `"auto"` for vault-consistent behavior.

---

## Engineering Lens Findings

### Failure Mode Analysis & Correctness
* **E1: Malformed Windows CRLF Line Endings (Severity: 🎯 Must-Address)**
  * *Finding:* On Windows platforms, files typically use `\r\n` endings. Replacing `\n` with `  \n` on a CRLF line produces `\r  \n`, placing the carriage return before the hard-break spaces. This is malformed and corrupts markdown parsers and pre-commit checks.
  * *Suggestion:* Strip line endings (`\r\n` or `\n`) before inspecting and transforming line contents, then re-attach the appropriate ending.

* **E2: Paragraph Break Merging (Severity: 🎯 Must-Address)**
  * *Finding:* Paragraphs are separated by blank lines or lines containing only spaces. The rule "not followed by another `\n`" fails on whitespace-filled lines (e.g. `\n   \n`), treating them as text breaks and incorrectly inserting spaces, merging two paragraphs into one.
  * *Suggestion:* Ensure any line that contains only whitespace is preserved verbatim without transformation. Also, do not append a hard break to a line if the subsequent line is empty or whitespace-only.

* **E3: Markdown Block Syntax Corruption (Severity: 💡 Recommendation)**
  * *Finding:* Table rows (e.g. `| Col 1 | Col 2 |`), lists (e.g. `- Item`), headings (`# Title`), and thematic breaks (`---`) are block elements. Appending `  ` to table separators/rows violates Markdown specifications and can break table compilation in Pandoc.
  * *Suggestion:* Exclude lines starting with headings (`#`), table rows (`|`), list item markers (`-`, `*`, `+`, `1.`), thematic breaks (`---`), or HTML blocks from the soft-line-break transformation.

---

## Cross-Lens Insights

* **E3 × P2 (Layout Integrity vs Pandoc Support):**
  Protecting tables, headings, and list items from trailing space insertions avoids rendering corruption (Product) and guarantees clean Pandoc compilation without parsing errors (Engineering).

* **P1 × E1 (Config Robustness & OS Portability):**
  Supporting native TOML booleans and CRLF line endings ensures Syntagmax behaves robustly on all client setups without crashing during configuration parsing or producing malformed files.

---

## Verdict & Action Plan

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

### Specific Edits Suggested

1. **Under Requirements in [strict-line-breaks.spec.md](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/docs/specs/strict-line-breaks.spec.md) (update transformation and validation rules):**
   * **Replace:**
     ```markdown
     - New field `strict_line_breaks` on `ObsidianDriverConfig` in `config.py`
     - Accepted values (case-insensitive):
       - `on` or `true` — strict mode (standard Markdown, no transformation)
       - `off` or `false` — Obsidian-style relaxed breaks (apply `  \n` transformation)
       - `auto` — read `strictLineBreaks` from Obsidian's `app.json`
     ```
   * **With:**
     ```markdown
     - New field `strict_line_breaks` on `ObsidianDriverConfig` in `config.py`, accepting string or native boolean values
     - Accepted values (case-insensitive for strings):
       - `on` / `true` / boolean `True` — strict mode (standard Markdown, no transformation)
       - `off` / `false` / boolean `False` — Obsidian-style relaxed breaks (apply `  \n` transformation)
       - `auto` — read `strictLineBreaks` from Obsidian's `app.json`
     ```

   * **Replace:**
     ```markdown
     ### Rules

     1. A `\n` that is NOT preceded by two spaces or a backslash, and NOT followed by another `\n`, is replaced with `  \n`.
     2. Paragraph breaks (`\n\n`) are left untouched.
     3. Already-existing hard breaks (`  \n` or `\\\n`) are not doubled.
     4. Lines inside fenced code blocks (` ``` `) are never modified.
     5. The transformation is applied at extraction time, affecting both TextBlock content and artifact `contents` fields.
     ```
   * **With:**
     ```markdown
     ### Rules

     1. Lines inside fenced code blocks (` ``` `) are never modified.
     2. Lines consisting only of whitespace (empty lines or paragraph separators) are never modified.
     3. Lines preceding an empty or whitespace-only line are never modified (to preserve paragraph breaks).
     4. Markdown block-level elements (headings starting with `#`, table rows starting with `|`, list items starting with `- `, `* `, `+ ` or numbers like `1. `, thematic breaks starting with `---`, or HTML blocks) are never modified.
     5. Already-existing hard breaks (trailing `  ` or `\`) are not doubled.
     6. Any other line is appended with `  ` before its line ending (`\n` or `\r\n`), preserving the original line ending format.
     7. The transformation is applied at extraction time, affecting both TextBlock content and artifact `contents` fields.
     ```

2. **Under Proposed Solution (update step 1 and 5):**
   * **Replace:**
     ```markdown
     1. Add `strict_line_breaks` field to `ObsidianDriverConfig` with default `"on"`, accepting `on`/`true`/`off`/`false`/`auto`
     ...
     5. Implement a code-block-aware line-break transformation function `apply_soft_line_breaks(text: str) -> str`
     ```
   * **With:**
     ```markdown
     1. Add `strict_line_breaks` field to `ObsidianDriverConfig` as `str | bool` with default `"on"`, accepting `on`/`true`/`off`/`false`/`auto`/`True`/`False`. Normalizes value to lowercase string.
     ...
     5. Implement a code-block-aware, CRLF-safe, and block-syntax-aware line-break transformation function `apply_soft_line_breaks(text: str) -> str`
     ```
