# Spec Critique: Content Files (Headingless File Rendering)

This report challenges the specification in [content-files.spec.md](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/docs/specs/content-files.spec.md) through a dual Product and Engineering review to ensure design correctness, usability, and technical soundness before implementation.

---

## Executive Summary

The proposed "Content Files" feature is highly valuable for requirements management, enabling users to write folder notes or introductions (e.g., `_contents_.md`) that render cleanly without artificial heading blocks.

However, the specification contains a **critical layout defect** regarding file sorting (X1), which would cause headingless content to be visually merged under preceding sibling subheadings. It also introduces a minor coupling risk by placing a global publishing configuration under a specific driver's namespace (E1).

With the updates detailed below, this feature is safe and ready to implement.

**Verdict**: ⚠️ **PROCEED WITH UPDATES**

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **X1** | Both | 🎯 Must-Address | Scope × UX / Layout | Sibling sorting can interleave the content file, causing its headingless text to render under an unrelated sibling's heading. | Implement a custom tuple-based sorting key in the rendering loop to guarantee the content file sorts first at its directory level. |
| **E1** | Engineering | 💡 Recommendation | Architecture Soundness | Placing `contents_marker` under `[drivers.obsidian]` couples the general publish module to a specific driver's configuration. | Move the configuration option to `PublishConfig` (`publish.yaml` or global `[publish]` table). |
| **P1** | Product | 💡 Recommendation | Edge Cases & UX | A case-sensitive match against the file stem may fail on case-insensitive filesystems (Windows/macOS) if the casing differs. | Match the content file stem case-insensitively. |
| **P2** | Product | 💡 Recommendation | Edge Cases & UX | The configurable marker is not validated, which could lead to empty/whitespace values or invalid path characters. | Add a Pydantic validator to restrict the marker to non-empty strings without directory separators. |

---

## Detailed Findings & Analysis

### 🎯 Must-Address

#### X1: Content File Sorting
- **Category**: Scope × UX / Layout
- **Description**: Currently, files are sorted alphabetically by their relative path string. If a user configures `contents_marker = "index"`, a directory structure containing `Chapter/characteristics.md`, `Chapter/index.md`, and `Chapter/requirements.md` will sort the files in that order. Because `index.md` emits no heading, its content will render immediately after `characteristics.md`, placing it visually inside the `## characteristics` section.
- **Impact**: Severe rendering/layout bug that confuses the reader and breaks document structure.
- **Suggestion**: Ensure that content files are sorted first within their directory. In [publish.py](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/src/syntagmax/publish.py#L416), sort `input_block.files` before rendering using a custom tuple key:
  ```python
  def make_sort_key(file_record):
      components = decompose_file_path(file_record.path, record_dir)
      key = []
      for idx, comp in enumerate(components):
          is_last = (idx == len(components) - 1)
          if not is_last:
              key.append((2, comp))  # Subdirectories sort last
          else:
              if comp.lower() == contents_marker.lower():
                  key.append((0, comp))  # Content file sorts first
              else:
                  key.append((1, comp))  # Other files sort in the middle
      return key
  ```

---

### 💡 Recommendations

#### E1: Configuration Placement
- **Category**: Architecture Soundness / Separation of Concerns
- **Description**: The spec places `contents_marker` in the `ObsidianDriverConfig` class under `[drivers.obsidian]`. However, the rendering pipeline operates on a general `BlockTree` and is driver-agnostic. If a user only uses the `markdown` driver, having to configure a publishing layout feature inside `[drivers.obsidian]` is unintuitive and violates the separation of concerns.
- **Impact**: Poor developer/user experience and tight coupling of the publish module to Obsidian configuration.
- **Suggestion**: Relocate `contents_marker` to `PublishConfig` in [publish_config.py](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/src/syntagmax/publish_config.py#L63) or the global `[publish]` table in `syntagmax.toml`.

#### P1: Case Sensitivity of Marker
- **Category**: Edge Cases & UX
- **Description**: The spec requires an exact (case-sensitive) match on the file stem. On Windows or macOS, a user might name a file `_CONTENTS_.md` or `_Contents_.md` (which are treated identically by the OS), but the publisher would fail to match it and would generate an unwanted `## _CONTENTS_` heading.
- **Impact**: Inconsistent cross-platform behavior and unexpected headings.
- **Suggestion**: Implement case-insensitive comparison (e.g. `components[-1].lower() == contents_marker.lower()`).

#### P2: Marker Validation
- **Category**: Edge Cases & UX
- **Description**: If a user configures `contents_marker` as an empty string, whitespace, or includes invalid filename/path characters (such as `/` or `\`), it could cause unexpected matching behavior or crashes.
- **Impact**: Potential runtime errors or invalid document output.
- **Suggestion**: Add a Pydantic field validator to verify that `contents_marker` is a non-empty, non-whitespace string containing no directory separator characters.
