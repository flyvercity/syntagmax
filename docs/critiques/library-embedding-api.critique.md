# Dual-Lens Critique Report: Library-First Embedding API for Syntagmax

> **Critique Pass:** 1 (First Pass)  
> **Target Specification:** `docs/specs/library-embedding-api.spec.md`  
> **Date:** 2026-09-28  
> **Status:** Complete  

---

## Executive Summary

This report presents Critique Pass 1 for the `docs/specs/library-embedding-api.spec.md` specification. The specification outlines a small, additive, sanctioned embedding API surface (`syntagmax.api`) along with three supporting core capabilities (`impact.task_dir` redirection, structured diagnostics, and an Obsidian-focused driver write seam).

Overall, the specification is mature, highly contextualised, and directly addresses the core offloading requirements identified during GUI integration planning. It strictly adheres to the principle of preserving CLI behaviour while providing a clean in-process Python API for host applications.

However, the dual-lens evaluation revealed several critical architectural ambiguities and operational edge cases that must be addressed prior to implementation. Specifically, discrepancies exist between internal core error models (`ReportError`) and public facade data types (`Diagnostic`), edge cases in the Obsidian write seam (`create_artifact` ID allocation, `delete_artifact` file removal, and YAML attribute deletion) are underspecified, thread-safety for multi-threaded host servers is unaddressed, and atomic file-writing safety controls are missing.

**Verdict:** ⚠️ **PROCEED WITH UPDATES** — The core design is sound, but the identified must-address items must be clarified in the specification before proceeding to implementation.

---

## Product Lens Findings

### 1a. Problem Validation
- The problem statement clearly establishes why an in-process library embedding facade is necessary. Re-implementing pipeline execution, fabricating CLI-shaped `Params` dictionaries, and parsing flat diagnostic text in host applications creates unnecessary coupling and maintenance friction.
- The scope is appropriate and strictly bounded. Non-goals explicitly exclude Git write operations, authentication, non-Obsidian write drivers, and async/HTTP concepts.

### 1b. User Value Assessment
- User value for host application developers (such as the Syntagmax Web GUI team) is high. The `syntagmax.api.Session` interface encapsulates complex core pipeline orchestration into intuitive read, query, analysis, and edit calls.
- **Finding (P1):** `Session.edit()` currently returns `None`. For embedders, editing an artifact typically requires immediately refreshing the UI with the modified object. Forcing embedders to issue a secondary `Session.get(aid)` call introduces unnecessary ergonomics friction and potential race conditions.

### 1c. Alternative Approaches
- The specification correctly references the brainstorm evaluation (`docs/brainstorms/CORE_OFFLOAD_REPORT.md`, Approach B) that selected an additive `syntagmax.api` facade over either loose free functions or a disruptive CLI-wide refactor. This strikes the optimal balance between host ergonomics and core stability.

### 1d. Edge Cases & User Experience
- **Finding (P2):** `Session.search(q)` semantics are underspecified regarding whether search queries match against artifact body text (`contents`) or strictly metadata attributes (`fields`, `aid`, `atype`).
- **Finding (X2):** Write operations under the Obsidian driver exhibit several unaddressed edge cases:
  - `create_artifact`: If `aid` is omitted (`aid=None`), the specification does not detail how artifact IDs are allocated or verified against existing metamodel constraints.
  - `edit_artifact`: Passing a attribute value of `None` (e.g. `fields={'status': None}`) is not explicitly defined as removing the key versus writing an empty string.
  - `delete_artifact`: Deleting an artifact from a Markdown file containing multiple artifacts must remove the fragment, whereas deleting the sole artifact in a file leaves an ambiguous state regarding file removal versus leaving an empty document.

### 1e. Success Measurement
- The acceptance criteria include unit tests, parity assertions, golden-output CLI verification, and Windows path tests.
- Performance targets (e.g. baseline response latency for `Session.artifacts()` on repositories with 1,000+ artifacts) are not explicitly specified, though initial single-shot execution expectations match current core performance.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
- The separation between internal core models (`Artifact`, `ReportError`) and public facade dataclasses (`ArtifactView`, `Diagnostic`) is an excellent architectural boundary decision that prevents internal refactoring from breaking embedders.
- **Finding (X1):** Discrepancy between `ReportError` and `Diagnostic` models:
  - `ReportError` in `src/syntagmax/report.py` contains `(message, category, input_record, artifact_id, artifact_type, file_path, line_range)`.
  - `Diagnostic` in `src/syntagmax/api.py` requires `(severity, artifact_id, rule, category, location, message)`.
  - `ReportError` currently lacks a `rule` attribute, and `Diagnostic` collapses `file_path` and `line_range` into an unspecified `location` string. Mapping between these types is underspecified in Task 3 and Task 6.
- **Finding (E3):** Inconsistent method signature in `capabilities()`: Section R1.7 names the parameter `record_or_driver`, whereas Task 6 names it `driver_or_record`.

### 2b. Failure Mode Analysis
- **Finding (E1):** The Obsidian write seam (`edit_artifact`, `create_artifact`, `delete_artifact`) modifies files directly on disk without specifying atomic file writing mechanisms (e.g. writing to a temporary file in the same directory and performing `os.replace`). Direct in-place writes risk leaving corrupted files if process execution fails mid-write.

### 2c. Security & Privacy Review
- **Finding (E1 - Path Traversal):** `create_artifact` accepts a `target_file` path parameter. If supplied directly from user input via an embedding host, `target_file` could contain path traversal sequences (e.g. `../../etc/passwd`) escaping `config.root_dir`. Path normalization and boundary validation are required inside `syntagmax.api`.

### 2d. Performance & Scalability
- `Session.reload()` triggers full pipeline re-execution (`extract → map → pids → tree → analyse_tree`). While acceptable for current repository sizes, mutating a single artifact in large projects will incur full re-parsing overhead. This should be explicitly noted as a known trade-off for Phase 1.

### 2e. Testing Strategy
- The testing strategy is comprehensive, covering CLI parity, golden-output reports, Obsidian CRUD round-trips, Windows path handling, and `task_dir` redirection.

### 2f. Operational Readiness
- **Finding (E2):** Web GUI hosts (e.g. FastAPI application servers) execute request handlers across multi-threaded worker pools. `Session` maintains internal mutable cache state (`_artifact_map`) and provides a `reload()` method without internal lock synchronization (`threading.Lock`). Concurrent API calls could trigger race conditions during cache invalidation.

### 2g. Dependencies & Integration Risks
- All additions rely strictly on stdlib dataclasses and existing core modules, introducing no external third-party dependencies.

---

## Cross-Lens Insights

The product and engineering perspectives converge on two primary critical areas:

1. **Diagnostics Convergence (X1):** Product features (Analysis tab issue binding) and Engineering reliability (single source of truth without duplicated error lists) both depend on a clean, unified diagnostic model. Rebuilding diagnostic emissions around `ReportError` with `severity` and `rule` attributes guarantees byte-identical CLI outputs while giving embedders structured, object-bound diagnostics.
2. **Write Seam Rigour & Safety (X2 & E1):** Providing programmatic artifact mutation in Obsidian files delivers high product value, but requires strict engineering safety: atomic file replacements, clear multi-artifact block deletion rules, explicit `None` attribute semantics, path boundary enforcement, and thread safety.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| X1 | Both | 🎯 | Diagnostics Architecture | Inconsistency between `ReportError` attributes (`input_record`, `file_path`, `line_range`) and public `Diagnostic` attributes (`rule`, `location`), with `rule` missing in core `ReportError`. | Harmonise `ReportError` and `Diagnostic` models by adding `rule: str \| None` to `ReportError` and explicitly specifying the mapping rules from `ReportError` to `Diagnostic`. |
| X2 | Both | 🎯 | Write Seam Edge Cases | Underspecified behavior for Obsidian write operations: ID allocation when `aid=None` in `create_artifact`, handling `fields={'key': None}` in `edit_artifact`, and multi-artifact file deletion semantics in `delete_artifact`. | Define exact contracts: require non-None `aid` (or specify auto-generation rules) for `create_artifact`, treat `None` values in `edit_artifact` as attribute deletions, and specify file deletion versus content removal rules for `delete_artifact`. |
| E1 | Engineering | 🎯 | Security & Resilience | Lack of atomic file writing in `Extractor` write methods, and missing path traversal validation for `target_file` in `create_artifact`. | Implement atomic file replacement (`tempfile` + `os.replace`) for all write seam operations, and enforce path boundary checks verifying `target_file` resides within `config.root_dir`. |
| E2 | Engineering | 💡 | Concurrency & Thread-Safety | `Session` internal cache (`_artifact_map`) and `reload()` lack thread locks, posing race condition risks when embedded in multi-threaded web application servers (e.g. FastAPI). | Add `threading.Lock` within `Session` to serialize `reload()` execution and lazy artifact graph generation. |
| P1 | Product | 💡 | Developer Ergonomics | `Session.edit()` returns `None`, forcing embedders to issue a secondary `Session.get()` request to inspect updated artifact state. | Update `Session.edit()` to return `ArtifactView`, providing immediate feedback on updated artifact state. |
| E3 | Engineering | 💡 | Interface Parity | Mismatch in method parameter naming between spec requirement R1.7 (`record_or_driver`) and Task 6 (`driver_or_record`). | Standardise method signature across spec and code as `capabilities(driver_or_record: str \| InputRecord) -> set[str]`. |
| P2 | Product | 🤔 | Query & Search Semantics | Underspecified search scope for `Session.search(q)` regarding whether matching extends to artifact body text (`contents`) or only frontmatter fields. | Clarify in specification whether `search(q)` scans body text (`contents`) alongside metadata attributes, and define multi-term matching rules. |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

The design presented in `docs/specs/library-embedding-api.spec.md` is sound and aligns with the project constitution and core offload strategy. However, implementation should be paused until the 3 Must-Address (🎯) items and 3 Recommendations (💡) are incorporated into the specification document.

---

## Remediation & Suggested Edits

The following specific amendments are proposed for `docs/specs/library-embedding-api.spec.md`:

### 1. Remediation for X1 (Diagnostics Model Harmonisation)
- **In Section R2 (Requirement 10 & 11):** Update to specify that `ReportError` in `src/syntagmax/report.py` gains both `severity: str = 'error'` and `rule: str | None = None`.
- **In Task 6 (`syntagmax.api` facade):** Clarify the exact field mapping from `ReportError` to `Diagnostic`:
  - `severity = report_error.severity`
  - `artifact_id = report_error.artifact_id`
  - `rule = report_error.rule or report_error.category`
  - `category = report_error.category`
  - `location = f"{report_error.file_path}:{report_error.line_range}"` if `file_path` is present, else `""`
  - `message = report_error.message`

### 2. Remediation for X2 & E1 (Obsidian Write Seam & Security Rules)
- **In Section R3 & Task 4 (Write Seam):**
  - Require `create_artifact` to enforce that `aid` is explicitly provided, create any missing parent directories for `target_file`, and validate that `target_file` resolves within `config.root_dir` (raising `ValueError` on traversal attempts).
  - Specify that `edit_artifact` with a field set to `None` removes that attribute key from the file's YAML frontmatter.
  - Specify that `delete_artifact` removes the specific marked fragment from multi-artifact Markdown files, and deletes the underlying file if no artifact content remains.
  - Mandate that all file writes in the Obsidian extractor use atomic temporary files (`tempfile.NamedTemporaryFile` in the target directory followed by `os.replace`).

### 3. Remediation for E2, P1, and E3 (Session Ergonomics & Parity)
- **In Section R1 & Task 5/6:**
  - Add internal `threading.Lock` initialization to `Session`, acquiring the lock during `Session.reload()` and during initial lazy `ArtifactMap` computation.
  - Update `Session.edit(...)` signature to return `ArtifactView` (the updated view post-reload).
  - Standardise parameter name in `capabilities` to `Session.capabilities(driver_or_record: str | InputRecord) -> set[str]`.

---

Would you like me to apply these changes? (all / select / none)

---

## Resolution (Pass 1 applied)

**Selection: all.** All 3 must-address (X1, X2, E1) and 3 recommendations (P1, E2, E3), plus the P2 clarification, were applied to `docs/specs/library-embedding-api.spec.md`:

- **X1** — `ReportError` gains `rule: str | None` (R2.11, Task 2); explicit `ReportError → Diagnostic` mapping added (R2.14, Task 6).
- **X2** — `create_artifact` requires non-`None` `aid` + creates parent dirs; `edit_artifact` `None` value deletes the YAML key; `delete_artifact` removes the fragment and deletes the file when it was the sole artifact (R3.17, Task 4).
- **E1** — atomic writes (`tempfile` + `os.replace`) and `target_file` path-traversal validation against `root_dir` (R3.18, Task 4).
- **E2** — `Session` holds a `threading.Lock` guarding lazy load + `reload()`; large-repo full-reparse noted as a Phase-1 trade-off (R1.4, Task 5).
- **P1** — `Session.edit()`/`create()` now return the updated `ArtifactView` (R1.7, Task 6).
- **E3** — `capabilities(driver_or_record: str | InputRecord)` standardised across R1.7 and Task 6.
- **P2** — `search(q)` scope defined: case-insensitive over `aid`/`atype`/all `fields` incl. `contents`, AND semantics across terms (R1.5, Task 5).
