# Spec: Obsidian Attachment Folder Path Integration

## Problem Statement

When Obsidian users store images/attachments in a configured folder (e.g., `attachments/pics/`), Syntagmax's publishing pipeline cannot resolve `![[image.png]]` references because the attachment folder isn't part of any declared input record. The fix is to read Obsidian's `app.json` settings and use the `attachmentFolderPath` as an additional search location during image resolution.

## Requirements

- Configuration lives under `[drivers.obsidian]` in `config.toml`
- Two new options: `integration` (bool) and `root` (optional path override)
- Feature only affects the publish pipeline (image resolution), not extraction
- If integration is enabled but `.obsidian/app.json` can't be read or `attachmentFolderPath` isn't set, log a warning and fall back to existing behavior
- Note-relative attachment paths (starting with `./`) are resolved relative to the source note's directory, not the project root

## Configuration

```toml
[drivers.obsidian]
integration = true
root = ".obsidian-custom"  # optional, defaults to <base_dir>/.obsidian
```

- `integration` — enable reading Obsidian vault settings (default: `false`)
- `root` — optionally point the tool to another directory instead of `<project-root>/.obsidian`

## Obsidian Settings Source

The tool reads `app.json` from the Obsidian directory (`.obsidian` by default, or the configured `root`). The relevant field is `attachmentFolderPath`:

```json
{
  "attachmentFolderPath": "attachments/pics"
}
```

### Path Resolution Rules

Obsidian supports multiple attachment folder configurations:

1. **Absolute vault-relative path** (e.g., `"attachments/pics"`): resolved relative to the project base directory.
2. **Note-relative path** (e.g., `"./attachments"` or `"."`): resolved relative to the current source note's directory using `context.source_file_path`.

The implementation must detect note-relative paths (starting with `./` or equal to `.`) and resolve them dynamically per-note during publishing.

## Proposed Solution

1. Extend `ObsidianDriverConfig` with `integration: bool = False` and `root: str | None = None`
2. Implement an Obsidian settings reader that lazily reads `.obsidian/app.json` (or custom root) and extracts `attachmentFolderPath`, with explicit error handling for filesystem and JSON failures
3. Lazy-load the attachment folder configuration during `RenderContext` initialization (not in the `Config` constructor) to avoid I/O side-effects during non-publish commands and tests
4. In `resolve_image_to_manifest()`, check the attachment folder **first** (O(1) filesystem lookup) before falling back to the vault-wide input record scan (O(N))

## Error Handling

The settings reader must explicitly catch and handle the following exceptions when reading `app.json`, logging a warning and returning `None` in each case:

- `FileNotFoundError` — `.obsidian/app.json` does not exist
- `PermissionError` — file exists but is not readable
- `json.JSONDecodeError` — file contains malformed JSON

No other exceptions should be silently swallowed.

## Task Breakdown

### Task 1: Extend `ObsidianDriverConfig` with integration fields

- **Objective:** Add `integration` and `root` fields to the existing `ObsidianDriverConfig` pydantic model.
- **Implementation:** In `src/syntagmax/config.py`, add two new fields to `ObsidianDriverConfig`: `integration: bool = False` and `root: str | None = None`.
- **Test:** Write a unit test confirming that `config.toml` with `[drivers.obsidian]\nintegration = true\nroot = ".obsidian-custom"` parses correctly into the config model, and that defaults work when fields are absent.
- **Demo:** A config file with `[drivers.obsidian]\nintegration = true` loads without errors, and the config object reflects the new fields.

### Task 2: Implement Obsidian settings reader

- **Objective:** Create a utility that reads `.obsidian/app.json` and extracts `attachmentFolderPath`.
- **Implementation:** Add a function `read_obsidian_attachment_path(base_dir: Path, root_override: str | None) -> str | None` in a new module `src/syntagmax/obsidian_settings.py`. It resolves the `.obsidian` directory (or the override), reads `app.json`, parses JSON, and returns the raw `attachmentFolderPath` string (not yet resolved to an absolute path — resolution depends on whether it's note-relative). Explicitly catches `FileNotFoundError`, `PermissionError`, and `json.JSONDecodeError`, logging a warning and returning `None` for each.
- **Test:** Unit tests covering: (a) successful read with `attachmentFolderPath` present, (b) missing `app.json` logs warning and returns `None`, (c) malformed JSON logs warning and returns `None`, (d) permission error logs warning and returns `None`, (e) missing key in valid JSON logs warning and returns `None`, (f) custom root override is respected.
- **Demo:** Calling the utility on a mock `.obsidian/app.json` with `"attachmentFolderPath": "attachments/pics"` returns the string `"attachments/pics"`.

### Task 3: Wire settings into RenderContext (lazy loading)

- **Objective:** Make the Obsidian attachment path available during publishing without eagerly loading it in the `Config` constructor.
- **Implementation:** Store `drivers.obsidian` config (integration flag and root) on the `Config` instance. Add a cached property `obsidian_attachment_path: str | None` to `RenderContext` that calls `read_obsidian_attachment_path()` on first access (only when integration is enabled). This keeps `Config.__init__` free of `.obsidian/app.json` I/O.
- **Test:** Integration test with a tmp project verifying: (a) `RenderContext` lazily loads the path only when accessed, (b) non-publish commands don't trigger the read, (c) the cached property returns the same value on subsequent accesses.
- **Demo:** Creating a `Config` from a project without `.obsidian/` produces no warnings; accessing `context.obsidian_attachment_path` during publish triggers the read.

### Task 4: Extend image resolution with attachment folder lookup

- **Objective:** When resolving Obsidian `![[image.png]]` references, check the attachment folder first for O(1) resolution before falling back to the vault-wide scan.
- **Implementation:** In `publish_context.py`'s `resolve_image_to_manifest()`, in the `is_obsidian` branch:
  1. If `context.obsidian_attachment_path` is not `None`:
     - If the path is note-relative (starts with `./` or equals `.`): resolve relative to the source note's directory (`context.source_file_path`'s parent).
     - Otherwise: resolve relative to `base_dir`.
  2. Construct `resolved_folder / target_filename`, verify it exists and is within base_dir, and add to manifest.
  3. If found, return immediately (O(1)).
  4. If not found in attachment folder, fall back to the existing vault-wide input record scan.
- **Test:** (a) Image in vault-relative attachment folder resolves correctly. (b) Image in note-relative attachment folder (`./attachments`) resolves correctly. (c) Attachment folder lookup is skipped when integration is disabled. (d) Image outside base_dir via attachment folder is rejected with a warning. (e) Existing behavior (finding images in input records) still works as fallback. (f) Attachment folder takes priority over vault-wide scan.
- **Demo:** Publishing a document with `![[diagram.png]]` where `diagram.png` is in `attachments/pics/` produces `![diagram](images/attachments-pics-diagram.png)`.

### Task 5: Add end-to-end test with example fixture

- **Objective:** Validate the full flow from config loading through publishing with Obsidian attachment resolution.
- **Implementation:** Create a minimal test fixture (in `tests/` using tmp_path) that mimics a project with `.obsidian/app.json`, an attachment folder with an image, and a requirement referencing it. Run `render_block_tree` and verify the manifest contains the attachment image and the markdown output has rewritten references. Include a variant with note-relative path configuration.
- **Test:** The e2e test asserts correct manifest entries and markdown output for both vault-relative and note-relative configurations.
- **Demo:** Running the test suite passes, confirming the full pipeline works with Obsidian attachment integration.

### Task 6: Update documentation

- **Objective:** Ensure all user-facing documentation reflects the new Obsidian integration feature.
- **Implementation:** Update the following:
  1. `README.md` — Add a subsection under an appropriate heading documenting `[drivers.obsidian]` integration options (`integration`, `root`) with a usage example.
  2. `docs/reference/configuration.md` — Add the new `[drivers.obsidian]` fields to the configuration reference with descriptions, types, and defaults.
  3. `openwiki/` — Update relevant architecture or domain notes if they reference the publish image resolution flow or driver configuration.
- **Test:** Review rendered documentation for accuracy and completeness; verify all examples are syntactically valid TOML.
- **Demo:** A user reading the README or configuration reference can discover and configure the Obsidian attachment integration without consulting the spec.
