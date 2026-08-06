# Critique Report: Report Fixes Specification

**Target Specification:** `docs/specs/report-fixes.spec.md`  
**Date:** 2026-08-05  
**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Executive Summary

The `docs/specs/report-fixes.spec.md` specification addresses two valuable enhancements to Syntagmax: percent-encoding file paths in standard Markdown links (Issue #125) and enabling a configurable base output directory (`output_path` in `config.toml`, Issue #124).

Overall, the specification is clear, well-scoped, and aligns with user needs for Obsidian compatibility and output organization. However, the critique identified key technical edge cases—specifically cross-platform Windows path separator handling prior to URL encoding and CLI `--output` parameter fallback precedence—that should be refined in the specification prior to implementation.

---

## Product Lens Findings

### 1a. Problem Validation & Scope
- **Finding:** The scope is appropriately focused on issues #124 and #125 without feature creep.
- **Strength:** Directly addresses user friction when viewing report links containing spaces or Cyrillic characters in Markdown tools like Obsidian.

### 1b. User Value Assessment & Edge Cases
- **P1 (Recommendation / UX & Integration):** The specification does not account for `syntagmax ci install` commands (`cli_tools.py`), which generate GitHub Actions and GitLab CI workflow files with hardcoded `.syntagmax/outputs/` output paths. If a user sets `output_path = "reports/"` in `config.toml`, generated CI workflow artifacts will point to non-existent paths.
- **P2 (Recommendation / UX Edge Case):** Requirement 3 leaves display text `[filename]` unencoded. If a filename contains closing brackets `]`, raw rendering can break Markdown link syntax. While rare, acknowledging display escaping ensures robust link generation.

---

## Engineering Lens Findings

### 2a. Architecture Soundness & Cross-Platform Integrity
- **E1 (Must-Address / Cross-Platform Handling):** On Windows systems, `ReportError.file_path` may contain backslashes (`\`). Passing a path with backslashes directly to `urllib.parse.quote(path, safe='/')` results in percent-encoding backslashes to `%5C` (e.g. `dir%5Cfile.md`). This breaks Markdown links in cross-platform viewers.
  - *Mitigation:* Explicitly normalize backslashes to forward slashes (`path.replace('\\', '/')` or `PurePosixPath`) prior to calling `urllib.parse.quote()`.

### 2b. CLI Parameter Resolution & Precedence
- **E2 (Must-Address / Interface Consistency):** The top-level `rms` CLI group defines `--output` (which `analyze` consumes via `Params`), whereas `change report`, `trace`, and `publish` define their own subcommand-level `--output` options. The spec does not explicitly define the exact fallback hierarchy when top-level vs subcommand `--output` options are passed or omitted alongside `output_path`.
  - *Mitigation:* Clarify option resolution precedence across all commands: Subcommand `--output` > Top-level `--output` (if explicitly provided) > `config.output_dir()`.

### 2c. Operational Readiness & Testing
- **E3 (Recommendation / Edge Case Coverage):** Task 2 test requirements verify relative `output_path` values but omit testing absolute paths (e.g., `output_path = "/tmp/reports"`). Path resolution should be validated to ensure absolute paths resolve as expected.

---

## Cross-Lens Insights

1. **Windows Path Normalization before URL Encoding (E1 × P1):** Normalizing paths to POSIX format before URL encoding ensures both cross-platform technical correctness and a smooth user experience in Obsidian across macOS, Linux, and Windows.
2. **CLI Option Precedence & Predictability (E2 × P1):** Unifying how CLI `--output` flags interact with `config.output_dir()` across all subcommands prevents unexpected output locations when users run CLI commands in scripts or terminal sessions.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| E1 | Engineering | 🎯 | Architecture & Cross-Platform | `urllib.parse.quote()` on Windows backslashes produces `%5C`, breaking Markdown links. | Convert `file_path` backslashes to `/` before calling `urllib.parse.quote()`. |
| E2 | Engineering | 🎯 | Interface Consistency | Unclear resolution order between top-level `--output`, subcommand `--output`, and `output_path`. | Explicitly define fallback order: Subcommand `--output` > Top-level `--output` (if explicit) > `config.output_dir()`. |
| P1 | Product | 💡 | UX & Integration | `syntagmax ci install` commands generate CI workflows hardcoding `.syntagmax/outputs/`. | Note CI generator behavior in Task 4/5 or update CI templates to use `config.output_dir()`. |
| E3 | Engineering | 💡 | Testing Strategy | Task 2 lacks test cases for absolute `output_path` values. | Add unit test verifying absolute `output_path` resolution in `test_config.py`. |
| P2 | Product | 💡 | Edge Case | Brackets `]` in `filename` display text could break link parsing. | Note handling or escaping of special characters in `filename` display text in Task 1. |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

The specification is structurally solid and ready to move forward once the must-address items (Windows path normalization and CLI `--output` resolution order) and recommended refinements are incorporated.

---

## Remediation & Proposed Changes

Below are the exact suggested edits to `docs/specs/report-fixes.spec.md`:

### 1. Proposed Edit for Task 1 (Windows Path Normalization & Display Text)

```diff
-  - In the non-wiki branch, apply `urllib.parse.quote(path, safe='/')` to the path before inserting it into the `[text](url)` construct.
+  - In the non-wiki branch, normalize `path` separators (`path.replace('\\', '/')`) and apply `urllib.parse.quote(posix_path, safe='/')` to the path before inserting it into the `[text](url)` construct.
```

### 2. Proposed Edit for Task 2 (Absolute Path Testing)

```diff
  **Test requirements:**
  - `ConfigFile` validates with and without `output_path` present.
  - Default: `Config.output_dir()` returns `<root_dir>/outputs/`.
  - Custom: with `output_path = "../reports"`, `Config.output_dir()` returns `<root_dir>/../reports` resolved.
+ - Absolute: with `output_path = "/tmp/reports"` (or OS equivalent), `Config.output_dir()` returns `Path("/tmp/reports")`.
```

### 3. Proposed Edit for Tasks 3 & 4 (CLI Output Precedence & CI Generator)

```diff
+ **CLI `--output` Resolution Rule:**
+ - Explicit subcommand `--output` takes highest precedence.
+ - Explicit top-level `rms --output` takes second precedence.
+ - If neither is provided, fall back to `config.output_dir()`.
```

---

*Report generated by scartill-sdd-lite critique.*
