# Critique: Pandoc DOCX Export Templates Spec

## Executive Summary

The Pandoc DOCX Export Templates specification ([docx-templates.spec.md](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/docs/specs/docx-templates.spec.md)) provides a clear and structured path to support corporate styling in exported Word documents. It correctly identifies the integration points within Pydantic, Pandoc, and the CLI execution flow.

However, the current spec contains a critical logic bug in template resolution: adding a specific override for one record will silently strip styling from all other records by falling back to `"none"` instead of the bundled default. Additionally, failing silently on missing templates and handling merged records in `--single` mode present robustness and usability risks.

With the updates proposed below, this feature will be robust, predictable, and ready for implementation.

---

## Product Lens Findings

### 1b. User Value Assessment
- **CLI Template Override (P1 - 💡 Recommendation):**
  Users often need to compile a requirements document for different audiences (e.g., drafts, internal reviews, or client-facing delivery) without committing configuration changes to version control. Adding a `--docx-template` CLI flag to the `publish` command provides immediate user value for one-off builds.

### 1d. Edge Cases & User Experience
- **Conflicting Overrides in Merged Output (E3 - 🎯 Must-Address):**
  When running `publish --single` to merge multiple records into one output file, Pandoc can only accept a single reference document. If merged records define different template overrides, using the first record's template is non-deterministic and ignores user intent. The user must be warned when overrides conflict.

---

## Engineering Lens Findings

### 2a. Architecture & Logic
- **Default Resolution Fallback Bug (E1 - 🎯 Must-Address):**
  Under Task 3's proposed logic, if the `docx-template` block is present in `publish.yaml` but `default-template` is omitted, the resolution path falls through to `None` (plain output). This means that simply defining a single override for one record will cause all other records to lose their styling.
- **Path Resolution Anchor (E4 - 💡 Recommendation):**
  The term "config directory" is ambiguous. Since `Config` can load `publish.yaml` from multiple fallbacks relative to the project directory, we should explicitly specify that paths are resolved relative to the project root config directory containing `config.toml` (`config._root_dir`).

### 2b. Failure Mode Analysis
- **Failing Closed on Missing Custom Templates (E2 - 🎯 Must-Address):**
  The spec suggests logging a warning and falling back to the bundled template if a custom template is not found. For automated CI/CD pipelines, a warning is easily missed, leading to incorrectly styled documents being published. The system should raise a `FatalError` if an explicitly defined template path is missing.

---

## Cross-Lens Insights

- **Validation vs. UX:** Failing closed on missing templates (E2) ensures engineering robustness, while also preventing the product risk of publishing unstyled documents to external clients.
- **Flexibility vs. Simplicity:** Adding a CLI override `--docx-template` (P1) resolves the need for temporary styling changes without requiring complex per-run configuration edits.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **E1** | Engineering | 🎯 **Must-Address** | Architecture / Logic | Omitted `default-template` causes fallback to `None` (no template) for non-overridden records when a `docx-template` section is present. | Adjust resolution order so that omitted `default-template` values fall back to the bundled `template.dotm`. |
| **E2** | Engineering | 🎯 **Must-Address** | Failure Modes | Non-existent custom template paths result in a silent fallback with a warning, masking configuration errors. | Raise a `FatalError` if a configured template path does not exist. |
| **E3** | Engineering | 🎯 **Must-Address** | Edge Cases | In `--single` mode, conflicting template overrides across records are silently ignored in favor of the first record's template. | Add a warning message if conflicting template configurations are detected when publishing with `--single`. |
| **P1** | Product | 💡 **Recommendation** | User Value / UX | No CLI override flag for DOCX template. | Add a `--docx-template` option to the CLI `publish` command. |
| **E4** | Engineering | 💡 **Recommendation** | Architecture / Logic | Ambiguity in the term "config directory" for path resolution. | Explicitly define the resolution anchor as the project configuration directory containing `config.toml` (`config._root_dir`). |
| **X1** | Both | 🤔 **Question** | Scope & UX | Lack of PDF template customization. | Clarify in the spec that PDF custom templates are out of scope for this spec but may be addressed in a future update. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

The specification is well-designed overall but requires specific logic corrections and robustness improvements before implementation.

---

## Remediation

Here are the proposed edits to [docx-templates.spec.md](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/docs/specs/docx-templates.spec.md):

### Suggested Spec Edits

#### 1. Update Resolution Order Section

```diff
 ### Resolution Order
 
-1. Per-record override in `docx-template.overrides.<record_name>` → use that path (or skip if `"none"`)
-2. `docx-template.default-template` → use that path (or skip if `"none"`)
-3. No `docx-template` section at all → use the bundled `template.dotm`
+0. CLI option `--docx-template` (if provided, overrides everything else for all records)
+1. Per-record override in `docx-template.overrides.<record_name>` if specified:
+   - If `"none"`, export without a template.
+   - Otherwise, resolve path relative to project config root (`config.toml` directory).
+2. `docx-template.default-template` if specified:
+   - If `"none"`, export without a template.
+   - Otherwise, resolve path relative to project config root.
+3. Otherwise (section absent, or config values are omitted/None), use the bundled `template.dotm`
```

#### 2. Update Task 3: Add template resolution helper function

```diff
 ### Task 3: Add template resolution helper function
 
 **Objective:** Create a function that resolves the correct template path for a given record.
 
 **Implementation guidance:**
 - Add a function `resolve_docx_template(pub_config: PublishConfig, record_name: str, config_root: Path) -> Path | None` (in `pandoc.py` or a new helper location)
 - Resolution logic:
-  1. If `pub_config.docx_template` is not None:
-     - Check `overrides.get(record_name)` — if `"none"`, return `None`; if a path, resolve relative to `config_root` and return it
-     - Check `default_template` — if `"none"`, return `None`; if a path, resolve relative to `config_root` and return it
-  2. If `pub_config.docx_template` is None (section absent), return the bundled default path: `Path(__file__).parent / 'resources' / 'template.dotm'`
- - Validate that the resolved path exists; if not, log a warning and fall back to bundled default (or `None` if explicitly set to `"none"`)
+  1. Check `pub_config.docx_template` overrides for `record_name`:
+     - If override is `"none"`, return `None`.
+     - If a path is specified, resolve relative to `config_root`. If the resolved file does not exist, raise a `FatalError`.
+  2. Check `pub_config.docx_template` default-template:
+     - If `"none"`, return `None`.
+     - If a path is specified, resolve relative to `config_root`. If the resolved file does not exist, raise a `FatalError`.
+  3. If no override/default path is defined, return the bundled default path: `Path(__file__).parent / 'resources' / 'template.dotm'`.
 
 **Test requirements:**
 - Unit test: absent `docx-template` → returns bundled template path
 - Unit test: `default-template` set to a path → resolves relative to config root
 - Unit test: per-record override → overrides the default
 - Unit test: `"none"` at any level → returns `None`
- - Unit test: nonexistent path → logs warning, falls back to bundled default
+ - Unit test: nonexistent path → raises `FatalError`
```

#### 3. Update Task 4: Wire template resolution into CLI `_run_pandoc_conversion`

```diff
 ### Task 4: Wire template resolution into CLI `_run_pandoc_conversion`
 
 **Objective:** Pass the resolved template to `pandoc.convert()` during DOCX export.
 
 **Implementation guidance:**
-- Modify `_run_pandoc_conversion` signature to accept an optional `reference_doc: Path | None` parameter
+- Modify `_run_pandoc_conversion` signature to accept an optional `reference_doc: Path | None` parameter.
 - Pass `reference_doc` to `pandoc.convert()` when format is `docx`
+- Add a new option `--docx-template` to the `publish` command in `cli.py` to allow manual template overrides.
 - In the `publish` command body (both single-file and per-record branches):
+  - If `--docx-template` CLI option is provided:
+    - If it is `"none"`, set template path to `None`.
+    - Otherwise, verify it exists (raising `FatalError` if missing) and use it as the template path.
+  - Otherwise, load the `PublishConfig` for the record(s) and call `resolve_docx_template()` to get the template path.
+  - In `--single` mode:
+    - Resolve the template path using the first record.
+    - Check if any other selected records have conflicting template resolutions. If so, print a warning to console indicating which template is being applied.
-  - Load the `PublishConfig` for the record(s)
-  - Call `resolve_docx_template()` to get the template path
-  - Pass it to `_run_pandoc_conversion()`
- - For `--single` mode (multiple records merged), use the first record's resolved template or the project-level default
```
