# Critique: Images in Change Report — Implementation Specification

This critique evaluates the implementation specification located at [images-in-change-report.spec.md](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/docs/specs/images-in-change-report.spec.md) through the Product and Engineering lenses.

## Executive Summary

The proposed specification is well-structured and provides a clear plan for implementing image/binary change reporting in Syntagmax. However, we have identified several gaps that must be addressed before proceeding to implementation. These include:
1. **Compliance with the global document-update rule**: Missing updates to existing reference docs (`CLI.md` and `configuration.md`).
2. **Worktree path resolution bug**: The path resolution logic fails when `config.base_dir()` is different from the repo root.
3. **Glob matching edge cases**: The extractor will crash/error on `.stmx` files matching the fallback `**/*` filter.

**Verdict**: ⚠️ **PROCEED WITH UPDATES** (resolvable must-address issues found).

---

## Product Lens Findings

### 1b. User Value Assessment
- **P1 (💡 Recommendation): Optimization of unchanged binary content rendering**
  - *Finding*: If a sidecar artifact's metadata changes (e.g., status or description) but the binary content itself is identical, rendering the "Binary Content" property table is redundant and adds visual noise.
  - *Suggestion*: Only render the "Binary Content" properties table when `binary_changed=True`.

- **P2 (💡 Recommendation): Avoid empty/placeholder dimension rows for non-images**
  - *Finding*: For non-image binary files (like PDFs), dimensions are not applicable. Showing `Dimensions: —` is confusing.
  - *Suggestion*: Omit the "Dimensions" row from the properties table if both `base_properties.width` and `target_properties.width` are `None`.

### 1e. Success Measurement
- **P3 (💡 Recommendation): Align binary summary statistics**
  - *Finding*: The spec introduces a single `binary_artifacts_changed` count. Text artifacts, however, are separated into added, modified, and removed.
  - *Suggestion*: Either clarify that `binary_artifacts_changed` is the sum of all three or track them separately as `binary_added`, `binary_modified`, and `binary_removed` to match the rest of the summary table.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
- **E1 (🎯 Must-Address): Skip sidecar files matching the glob pattern**
  - *Finding*: When a sidecar record uses a broad glob like `**/*`, the glob matches both the primary file (e.g. `diagram.png`) and the sidecar itself (`diagram.png.stmx`). Processing the sidecar file as a primary file in `SidecarExtractor.extract_blocks_from_file` results in an extraction failure.
  - *Suggestion*: Skip files ending in `.stmx` or `.syntagmax` inside `SidecarExtractor.extract_blocks_from_file`.

### 2b. Failure Mode Analysis / Path Resolution
- **E2 (🎯 Must-Address): Worktree path resolution bug**
  - *Finding*: The spec states: "resolve the primary file path (`artifact.location.loc_file`) relative to `base_path` / `target_path`." However, `loc_file` is relative to `config.base_dir()`, not the repo root (`base_path`/`target_path`). If `config.base_dir()` is different from the repo root (e.g., config is in a subdirectory or has `base = ".."`), simple joining will resolve to the wrong path.
  - *Suggestion*: Compute the relative path of `config.base_dir()` from the repository root, and use that relative path to offset `base_path` and `target_path` before joining with `loc_file`.

### 2g. Dependencies & Integration Risks
- **E3 (💡 Recommendation): Independent resolution of renamed primary files**
  - *Finding*: If a sidecar-managed file is renamed between commits, its `loc_file` path will differ between base and target revisions.
  - *Suggestion*: When computing hashes and extracting properties, resolve the base file path using `base_block.artifact.location.loc_file` and the target file path using `target_block.artifact.location.loc_file`.

### Compliance & Rules
- **E4 (🎯 Must-Address): Compliance with `spec-doc-update-rule` factoid**
  - *Finding*: The project's global factoid `spec-doc-update-rule` states that every spec must include a documentation update task covering ALL relevant documentation under `docs/reference/`, not just the README. The spec's Task 6 proposes creating `docs/reference/change-reports.md` but fails to mention existing reference files like `docs/reference/CLI.md` and `docs/reference/configuration.md` which document CLI commands and configuration.
  - *Suggestion*: Add explicit subtasks in Task 6 to update `docs/reference/CLI.md` and `docs/reference/configuration.md`.

---

## Cross-Lens Insights

- **UX × Engineering Simplification (P1, P2)**: Omitting unnecessary tables/rows when the binary content is unchanged or when dimensions are not applicable simplifies the rendering logic and improves report readability.
- **Traceability × Rules (E4)**: Fully updating the existing reference docs preserves documentation integrity and aligns with the project's strict specification guidelines.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 💡 | User Experience | Redundant binary content table when only sidecar metadata changed | Only render "Binary Content" table if `binary_changed=True`. |
| P2 | Product | 💡 | User Experience | Placeholders for dimensions on non-image binaries | Omit the "Dimensions" row if both base and target dimensions are `None`. |
| P3 | Product | 💡 | Success Measurement | Single count for binary changes lacks granularity | Track additions, modifications, and removals separately or clarify the combined count. |
| E1 | Engineering | 🎯 | Architecture | Crash/error when sidecar files match fallback glob filter | Skip files ending in `.stmx`/`.syntagmax` in `SidecarExtractor.extract_blocks_from_file`. |
| E2 | Engineering | 🎯 | Path Resolution | Path resolution fails if `config.base_dir()` is not repo root | Compute `rel_base` from repo root and offset `base_path`/`target_path` before joining. |
| E3 | Engineering | 💡 | Integration Risks | Renamed files have different `loc_file` paths in base and target | Resolve base and target file paths independently using their respective block locations. |
| E4 | Engineering | 🎯 | Compliance | Task 6 omits updates to `docs/reference/CLI.md` and `configuration.md` | Add explicit subtasks to update `CLI.md` and `configuration.md`. |

---

## Verdict & Action Plan

### Verdict: ⚠️ **PROCEED WITH UPDATES**

To resolve the must-address issues, we suggest updating `docs/specs/images-in-change-report.spec.md` as outlined in the remediation plan.
