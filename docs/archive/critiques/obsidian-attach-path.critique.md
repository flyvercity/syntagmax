# Critique Report: Obsidian Attachment Folder Path Integration Specification

## Executive Summary

The proposed specification for **Obsidian Attachment Folder Path Integration** addresses a key usability issue: resolving attachments stored in Obsidian's configured attachment folder (`attachmentFolderPath`) when publishing documents, without needing to declare the attachment folder as a scanned input record.

However, the specification has a critical gap regarding how Obsidian's settings are resolved:
1. **Relative/Note-Specific Paths**: Obsidian supports note-relative attachment folders (e.g., `"./attachments"` or same-folder configurations). The spec assumes all attachment folders are static and relative to the project root, which will break resolution for these configurations.
2. **Coupling/Eager I/O**: Eagerly reading `.obsidian/app.json` inside the `Config` constructor couples configuration parsing to external filesystem layouts and prints noisy warnings in tests or unrelated CLI commands.
3. **Lookup Performance**: Checking the attachment folder *after* the vault-wide input record search is inefficient ($O(N)$ vs $O(1)$).

**Verdict:** ⚠️ **PROCEED WITH UPDATES** (Must-address items exist but are readily resolvable).

---

## Product Lens Findings

### 1a. Edge Cases & User Experience
*   **Finding (P1 - 🎯 Must-Address):** Obsidian supports note-relative attachment folder configurations. For example, setting `"attachmentFolderPath": "./attachments"` means attachments are stored in a subfolder relative to the active note. The current spec resolves all paths relative to the project root, which will fail for note-relative configurations.
    *   *Suggestion:* Update the spec to dynamically resolve the attachment folder relative to the current source note's directory if the configured path starts with `./` (or is empty/relative).

---

## Engineering Lens Findings

### 2a. Architecture Soundness
*   **Finding (E1 - 💡 Recommendation):** Eagerly reading and parsing `.obsidian/app.json` within the `Config` initialization layer introduces early I/O and tight coupling. It can produce noisy warning messages during unit tests or non-publish CLI commands where the `.obsidian` directory is absent.
    *   *Suggestion:* Lazy-load the Obsidian settings during the publishing pipeline initialization or within `RenderContext`, rather than doing it in the core `Config` constructor.

### 2b. Failure Mode Analysis
*   **Finding (E2 - 🎯 Must-Address):** Task 2 specifies "Logs a warning on any failure." This is too vague and could lead to unhandled exceptions (e.g. `json.JSONDecodeError` for malformed JSON, `PermissionError` for locked files) crashing the runtime.
    *   *Suggestion:* Explicitly specify catching `FileNotFoundError`, `PermissionError`, and `json.JSONDecodeError` during `app.json` loading and parsing, falling back to a logged warning and returning `None`.

### 2c. Performance & Scalability
*   **Finding (E3 - 💡 Recommendation):** Task 4 proposes checking the attachment folder *after* the vault-wide input record file scan. The vault-wide scan is an $O(N)$ operation over all records. Since checking the attachment folder is an $O(1)$ filesystem path check, performing it *first* will significantly speed up resolution for attachments.
    *   *Suggestion:* Check the resolved attachment folder *first*. If the file exists there, resolve it immediately. Fall back to the vault-wide search only if the file is not found in the attachment folder.

---

## Cross-Lens Insights

*   **X1 (Dynamic Note-Relative Resolution):** Handling relative paths (e.g., `./attachments`) correctly aligns the engineering implementation with the real-world product usage of Obsidian, preventing broken links for notes located in subdirectories.
*   **X2 (Performance & Simplicity):** Checking the attachment folder first is both cleaner to implement and orders of magnitude faster for vaults with many notes, reducing publish latency.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 🎯 **Must-Address** | Edge Cases & UX | `attachmentFolderPath` can be relative to the note (e.g. `./attachments`), but spec only supports root-relative. | Resolve note-relative paths dynamically using `context.source_file_path`'s directory. |
| E1 | Engineering | 💡 **Recommendation** | Architecture | Eager reading of `app.json` in `Config` constructor causes I/O side-effects and noisy test logs. | Lazy-load the attachment path when initializing `RenderContext` or during publishing. |
| E2 | Engineering | 🎯 **Must-Address** | Failure Modes | Vague error handling for `app.json` reading/parsing can cause crashes. | Explicitly catch `FileNotFoundError`, `PermissionError`, and `json.JSONDecodeError` and log warning. |
| E3 | Engineering | 💡 **Recommendation** | Performance | Searching the attachment folder after vault-wide scan is slow ($O(N)$). | Check the attachment folder first ($O(1)$) before falling back to the vault-wide scan. |
