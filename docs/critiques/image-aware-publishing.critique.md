# Critique Report: Image-Aware Publishing Specification

## Executive Summary

The proposed specification for **Image-Aware Publishing** addresses a key usability issue: broken image paths in published documents and missing image embeds for sidecar artifacts. The overall design of introducing a `RenderContext` and `ImageManifest` is architecturally sound and integrates nicely with the existing publish pipeline in `publish.py`.

However, the specification contains a critical security risk (arbitrary file read/path traversal via relative paths pointing outside the workspace) and a technical flaw in the collision-handling algorithm (which can still result in file name collisions if parent directory names are identical).

**Verdict:** ⚠️ **PROCEED WITH UPDATES** (Must-address items exist but are readily resolvable).

---

## Product Lens Findings

### 1a. Problem Validation & Scope
*   **Finding (P1 - 💡 Recommendation):** The spec does not define the behavior for remote image references (e.g. `![logo](https://example.com/logo.png)`). Remote image URLs should be forbidden/ignored to prevent runtime network dependencies and download errors during publishing.
    *   *Suggestion:* Explicitly state that remote image URLs (e.g., those starting with `http://`, `https://`, or `//`) are forbidden and should be skipped (left unmodified with a logged warning).

### 1b. Edge Cases & User Experience
*   **Finding (P2 - 💡 Recommendation):** Standard markdown images can contain URL-encoded characters or spaces (e.g., `![diagram](assets/my%20diagram.png)`). If the system attempts to copy this path verbatim, the OS will fail to locate the file, causing warning logs and failing to copy.
    *   *Suggestion:* URL-decode the target paths (using `urllib.parse.unquote`) before performing file existence checks and copy operations.
*   **Finding (P3 - 💡 Recommendation):** The destination folder resolution for `--single` mode versus separate mode is ambiguous.
    *   *Suggestion:* Explicitly define the destination `images/` directory:
        *   For single mode: `output_dir = output_file_path.parent`, so images go to `output_dir / 'images'`.
        *   For separate mode: `output_dir = output_path`, so images go to `output_dir / 'images'`.

### 1c. Success Measurement
*   **Finding (P4 - 💡 Recommendation):** The specification has no success metrics defined.
    *   *Suggestion:* Add a Success Criteria section specifying that the HTML/Markdown preview renders images, and Pandoc output has no "image not found" warnings.

---

## Engineering Lens Findings

### 2a. Security & Privacy Review
*   **Finding (E1 - 🎯 Must-Address):** Standard markdown images can reference arbitrary paths relative to the source document, e.g., `![sensitive](../../../../etc/passwd)`. If unresolved, the CLI will blindly attempt to copy the file into the output directory, creating a Path Traversal / Arbitrary File Read vulnerability.
    *   *Suggestion:* Restrict image resolution to files located inside the project workspace directory (`base_dir`). If a resolved path falls outside `base_dir`, log a warning and skip the copying/rewriting for that reference.

### 2b. Architecture Soundness & Failure Modes
*   **Finding (E2 - 🎯 Must-Address):** The collision-handling strategy ("prefix with parent directory") is insufficient. If two files from different locations share the same parent folder name (e.g., `docs/images/diagram.png` and `src/images/diagram.png`), both would be rewritten to `images-diagram.png`, resulting in a collision.
    *   *Suggestion:* Flatten the relative path from the project root by replacing folder separators with dashes (e.g., `docs-images-diagram.png` vs `src-images-diagram.png`). This is simple, deterministic, and guarantees uniqueness because repository paths are unique.
*   **Finding (E3 - 💡 Recommendation):** The spec proposes `ImageManifest` maps `target_relative_path → source_absolute_path`. However, to achieve O(1) deduplication of already copied images during rendering, the renderer needs to check if a source absolute path has already been processed and reuse its assigned target filename.
    *   *Suggestion:* Maintain a bidirectional mapping or map `source_absolute_path → target_relative_path` to avoid copying the same image multiple times under different names.
*   **Finding (E4 - 💡 Recommendation):** Stale images from previous runs might accumulate in `.syntagmax/reports/images/`.
    *   *Suggestion:* Clean the `images/` output subdirectory before copying new files, or document that output cleanup is out of scope.

---

## Cross-Lens Insights

*   **X1 (Path Traversal Protection):** Restricting source images to the workspace folder addresses both an engineering security concern and a product reliability concern (making sure published reports are self-contained without leaking host-specific system files).
*   **X2 (Robust Naming Flattening):** Naming target files by flattening their relative path (e.g., `docs-images-diagram.png`) simplifies both implementation (no complex parent-directory search loops) and guarantees collision-free uniqueness for users.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| E1 | Engineering | 🎯 **Must-Address** | Security | Path traversal vulnerability via relative image paths outside workspace. | Check that resolved absolute paths reside within `base_dir`; skip and warn otherwise. |
| E2 | Engineering | 🎯 **Must-Address** | Failure Modes | Naming collision if parent folder names match (e.g., `a/images/f.png` vs `b/images/f.png`). | Flatten relative path from project root replacing `/` with `-` (e.g., `a-images-f.png`). |
| P1 | Product | 💡 **Recommendation** | Scope | Remote URLs (e.g. `https://...`) are not addressed. | Forbid remote URLs, skip from manifest and rewriting, and log a warning. |
| P2 | Product | 💡 **Recommendation** | Edge Cases | URL-encoded spaces/characters in markdown image paths break file copying. | URL-decode image paths before checking/copying files. |
| P3 | Product | 💡 **Recommendation** | Edge Cases | Ambiguous output directory resolution between `--single` and separate modes. | Specify `images/` is always placed relative to the parent of the output markdown file. |
| E3 | Engineering | 💡 **Recommendation** | Architecture | `ImageManifest` mapping structure makes source path deduplication complex. | Store `source_absolute_path → target_relative_path` (or bidirectional mapping) for O(1) deduplication. |
| P4 | Product | 💡 **Recommendation** | Success | No success metrics/criteria. | Add success criteria for Markdown viewers and Pandoc DOCX/PDF rendering. |
| E4 | Engineering | 💡 **Recommendation** | Architecture | Stale images accumulate in the output directory. | Clean/empty the `images/` directory at the start of publishing. |
