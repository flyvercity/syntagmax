# Spec Critique: Marker Renumber Command

## Executive Summary

This report evaluates the proposed specification for [markers-renumber.spec.md](../specs/markers-renumber.spec.md) under the Product Lens and the Engineering Lens.

The specification introduces a new CLI command to permanently assign sequential numeric IDs to unmarked fragment blocks (e.g., `[COM]`, `[NOTE]`) in source Markdown files. While the feature addresses a clear user need (creating stable anchors for cross-referencing and publishing), we have identified several issues—including one critical architectural bug risk:
1. **Marker Extraction vs. Replacement Scope Mismatch (Critical Bug Risk)**: A raw file-level regex substitution for `[MARKER]` will incorrectly match and replace literal marker tags inside code blocks, HTML comments, or within main `[REQ]` artifact blocks. Because these areas are ignored during extraction, this creates a major mismatch and corrupts non-narrative content.
2. **CLI Group & Option Inconsistencies**: The proposed `edit markers renumber` command introduces a nested subcommand hierarchy and options that differ from the existing flat `edit renumber` and `edit attrs` commands.
3. **No Section-Specific Filtering**: The command lacks the ability to restrict renumbering to a single input record (section), forcing users to run it across all files in the project.
4. **Tag Casing Mismatch**: Forcing uppercase replacement (e.g., `[COM 1]`) when the source file has lowercase markers (e.g., `[com]`) creates mixed-casing with existing lowercase closing tags (e.g., `[/com]`).

We recommend adopting an offset-based bottom-to-top replacement strategy to resolve the critical replacement scope risk, and refining the CLI options to align with the rest of the editing suite.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **E1** | Engineering | 🎯 **Must-Address** | Architecture Soundness | Raw file-level regex replacement will corrupt literal marker tags inside code blocks, comments, or main artifact blocks. | Implement offset-based bottom-to-top tag replacement using exact start/end character offsets from the parser. |
| **P1** | Product | 💡 **Recommendation** | User Experience | The nested CLI structure `edit markers renumber` is inconsistent with flat commands like `edit renumber`. | Simplify the command to `edit renumber-markers` or `edit markers-renumber` under the flat `edit` group. |
| **P2** | Product | 💡 **Recommendation** | Scope & User Journey | The command lacks a way to run renumbering on a specific input record (section), forcing changes project-wide. | Add a `--section` (or `--record`) option, matching `edit attrs`. |
| **P3** | Product | 💡 **Recommendation** | User Experience | Inconsistent config file option `-f, --config-file` vs. `edit renumber`'s positional `[CONFIG_PATH]`. | Support `[CONFIG_PATH]` as an optional positional argument to match `edit renumber`. |
| **P4** | Product | 💡 **Recommendation** | User Experience | Non-dry-run mode does not detail individual ID assignments in stdout, making verification difficult. | Log each assigned marker ID and file path during the writing phase. |
| **E2** | Engineering | 💡 **Recommendation** | Reliability | Normalizing marker tags to uppercase can mismatch lowercase closing tags (e.g., `[COM 1]` vs `[/com]`). | Preserve the original casing of the marker tag name as matched in the file. |
| **E3** | Engineering | 💡 **Recommendation** | Operational Readiness | Missing explicit instructions to write files using Unix-style line endings (LF) as mandated by global rules. | Enforce writing files with Unix-style line endings (`\n`). |
| **E4** | Engineering | 💡 **Recommendation** | Edge Cases | Ambiguity in parsing existing marker IDs containing leading zeros or negative integers. | Explicitly define valid existing numeric IDs as positive/non-negative integers. |

---

## Product Lens Findings

### User Experience
* **P1: Command Hierarchy Inconsistency (Severity: 💡 Recommendation)**
  * *Finding:* The CLI contains two flat commands under the `edit` group: `edit renumber` and `edit attrs`. Introducing `edit markers renumber` adds a nested `markers` subgroup for a single command, adding unnecessary CLI depth.
  * *Suggestion:* Flatten the hierarchy by renaming the command to `edit renumber-markers` or `edit markers-renumber` directly under the `edit` group.
* **P3: Config File Argument Inconsistency (Severity: 💡 Recommendation)**
  * *Finding:* `edit renumber` accepts the configuration file as a positional argument `[CONFIG_PATH]` (defaulting to `.syntagmax/config.toml`). The proposed spec uses `-f, --config-file`, introducing command inconsistency.
  * *Suggestion:* Accept `[CONFIG_PATH]` as an optional positional argument.
* **P4: Opaque Output during Non-Dry-Run Mode (Severity: 💡 Recommendation)**
  * *Finding:* The specification only prints a total summary when modifying files, making it hard for users to audit which files were modified and what IDs were assigned.
  * *Suggestion:* Log each assigned tag in the console (e.g., `Assigned [COM 1] to block at doc.md`).

### Scope & User Journey
* **P2: Lack of Section-Specific Filtering (Severity: 💡 Recommendation)**
  * *Finding:* The command requires `--all` and runs project-wide. Users frequently want to only modify or renumber a specific document (input record) to reduce the risk of accidental edits or merge conflicts.
  * *Suggestion:* Add a `--section <name>` (or `--record <name>`) option to restrict renumbering.

---

## Engineering Lens Findings

### Architecture Soundness
* **E1: Marker Extraction vs. Replacement Scope Mismatch (Severity: 🎯 Must-Address)**
  * *Finding:* `MarkdownExtractor` ignores code blocks, HTML comments, and main `[REQ]` artifact blocks when parsing. If the renumbering command runs a global regex replace for `[COM]` -> `[COM N]`, it will mistakenly replace literal example tags in code spans/blocks, comments, or main artifact blocks.
  * *Suggestion:* Adopt an offset-based replacement strategy. When parsing the markdown file, collect the exact start and end character offsets of the opening tags of unmarked blocks. In the write phase, sort these replacement targets in reverse order (bottom-to-top) and rewrite the file content by replacing the text at those exact offsets.

### Reliability
* **E2: Tag Casing Mismatches (Severity: 💡 Recommendation)**
  * *Finding:* Changing a lowercase marker like `[com]` to uppercase `[COM 1]` without changing the closing tag `[/com]` leaves mixed-case tags.
  * *Suggestion:* Detect and preserve the original tag name's casing (e.g., `com` or `Com` -> `[com 1]` or `[Com 1]`) when applying the replacement.

### Operational Readiness
* **E3: Line Ending (LF) Rules (Severity: 💡 Recommendation)**
  * *Finding:* The project requires Unix-style line endings (LF) for all code and file modifications.
  * *Suggestion:* Enforce Unix-style line endings (`\n`) when writing back the updated file content.

### Edge Cases
* **E4: Existing ID Parsing Ambiguity (Severity: 💡 Recommendation)**
  * *Finding:* The spec mentions collecting blocks where `id` is a "valid integer". Leading zeros (e.g. `[COM 005]`) or negative numbers should be defined to avoid parsing/calculation errors.
  * *Suggestion:* Explicitly parse IDs as integers using `int()` and check that they are non-negative.

---

## Cross-Lens Insights

* **Offset-Based Replacement vs. User Content Safety (E1 × P4):**
  Using offset-based replacement ensures that only actual parsed blocks are modified, eliminating the risk of corrupting user-written code examples or comments. Coupled with verbose console logs of every replacement, this gives the user complete confidence and visibility into what the command modified.
* **Scope Reduction & Blast Radius (P2 × E1):**
  Allowing users to target a single section (`--section`) reduces both the product blast radius (fewer file modifications to audit) and the engineering risk of large-scale file writes, while making tests easier to isolate.

---

## Verdict & Action Plan

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

### Specific Edits Suggested

1. **Under Requirements:**
   * Replace:
     ```markdown
     1. New CLI command group: `edit markers`
     2. New command: `edit markers renumber`
     ...
     7. Supports `--all` flag (required, following `edit renumber` pattern)
     ```
   * With:
     ```markdown
     1. New CLI command: `edit renumber-markers` (or `edit markers-renumber`) under the `edit` group
     ...
     7. Supports `--all` flag (renumber all unmarked blocks across all records) or `--section <name>` (restrict to a specific input record)
     ```

2. **Under CLI Interface:**
   * Replace:
     ```markdown
     syntagmax edit markers renumber [OPTIONS]
     ```
     options table and examples.
   * With:
     ```markdown
     syntagmax edit renumber-markers [CONFIG_PATH] [OPTIONS]
     ```
     Updated options table:
     * `[CONFIG_PATH]` | No | `.syntagmax/config.toml` | Path to config file
     * `--all` | No* | — | Renumber all unmarked blocks across the project
     * `--section <name>` | No* | — | Only renumber blocks in a specific input record
     * `--marker <name>` | No | — | Filter: only renumber blocks of a specific marker type
     * `--dry-run` | No | — | Show planned changes without modifying files
     
     *Either `--all` or `--section` is required.

3. **Under Algorithm:**
   * Replace:
     ```markdown
     7. Apply changes by regex substitution on the opening tag in the source file:
        - Match `[MARKER]` (case-insensitive) and replace with `[MARKER N]`
        - Only replace the first unmatched occurrence in document order
     8. Atomic writes: compute all changes in memory before writing any file.
     ```
   * With:
     ```markdown
     7. Determine the exact character offsets (start, end) of each unmarked opening tag during block extraction.
     8. Apply changes by performing string replacements at these offsets, sorted in reverse (bottom-to-top) order to prevent offset drift. Preserving the matched marker case (e.g. `com` vs `COM`).
     9. Atomic writes: compute all changes in memory before writing files with Unix-style line endings (LF).
     ```
