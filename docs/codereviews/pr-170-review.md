# PR Review: #170 - Library-first embedding API in support to GUI

**Reviewed**: 2026-09-28  
**Author**: @scartill  
**Branch**: `gui-adaptations` → `main`  
**Decision**: COMMENT (draft PR)

## Product & User Summary

- **The “Why” & What**: This PR adds a supported Python embedding API so a host application can read, search, analyse, and edit Syntagmax projects without reproducing core pipeline behavior. It also adds redirectable impact task output and structured diagnostics.
- **Key User-Facing & Behavioral Changes**:
  - `syntagmax.api.open_project()` provides a synchronous `Session` with artifact query, search, analysis, and write operations.
  - Obsidian artifacts gain edit, create, and delete support; other drivers advertise no write capabilities.
  - `impact.task_dir` can redirect generated tasks to an absolute or project-relative directory.
- **Risk Assessment & Migration Notes**: The facade is additive. Obsidian write methods modify project files directly and do not commit them. Consumers should review the two findings below concerning returned data isolation and YAML-safe serialization.
- **Testing Hints for QA**:
  1. Open a fixture project through the facade, read/query/search artifacts, and confirm the structured diagnostics agree with existing analysis output.
  2. Edit, create, and delete Obsidian artifacts in a temporary project; verify round-trip extraction and confirm `impact.task_dir` works with unset, relative, and absolute paths.

## Technical Summary

The implementation adds a cached facade over the existing analysis pipeline, an Obsidian write seam, a structured `ReportError` extension, and configurable task output resolution. Ruff passed for the changed runtime modules; the PR is draft, so this review is informational.

## Findings

### CRITICAL
None

### HIGH
None

### MEDIUM

- **Returned `ArtifactView.fields` aliases the cached artifact fields.** In `src/syntagmax/api.py:207`, the view receives `artifact.fields` directly. A host that changes `session.get(aid).fields[...]` changes the in-memory cached artifact without writing to disk; later reads then report data that does not exist in the source document. Copy the dictionary (including nested list values) when constructing the public view, or expose an immutable representation.
- **Create serializes field names and values into YAML without quoting or escaping.** In `src/syntagmax/extractors/markdown.py:566`, caller-provided values are interpolated directly into the YAML block. A string containing a newline can add unintended attributes, while YAML-special values can parse as a different type or make the newly written artifact unparseable. Serialize with a YAML emitter or quote/escape keys and values, then round-trip test multiline and YAML-special strings.

### LOW
None

## Validation Results

| Check | Result |
|---|---|
| Type check | Skipped |
| Lint | Pass (`uv run ruff check` on changed runtime modules) |
| Tests | Skipped (not run) |
| Build | Skipped |

## Files Reviewed

Modified runtime files: `src/syntagmax/api.py`, `src/syntagmax/config.py`, `src/syntagmax/errors.py`, `src/syntagmax/extractors/extractor.py`, `src/syntagmax/extractors/markdown.py`, `src/syntagmax/extractors/obsidian.py`, `src/syntagmax/publish_context.py`, `src/syntagmax/report.py`, and `src/syntagmax/tasks.py`.  
Planning/context: `docs/specs/library-embedding-api.spec.md`, `AGENTS.md`, and `openwiki/quickstart.md`.
