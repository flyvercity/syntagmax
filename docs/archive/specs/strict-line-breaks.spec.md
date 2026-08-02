# Spec: Strict Line Breaks Setting for Obsidian Driver

## Problem Statement

Obsidian has a "Strict line breaks" editor setting that controls how single newlines are rendered. When OFF (Obsidian's default), a single `\n` renders as a visible line break (`<br>`). When ON, it follows the standard Markdown spec where a single `\n` is collapsed to whitespace (requires `\n\n` for a paragraph break or trailing spaces/backslash for a hard break).

Syntagmax needs to match this behavior so that extracted artifact content and text blocks preserve the author's intended formatting when published or exported via Pandoc.

## Requirements

- New field `strict_line_breaks` on `ObsidianDriverConfig` in `config.py`, accepting string or native TOML boolean values
- Accepted values (case-insensitive for strings):
  - `on` / `"true"` / native boolean `true` — strict mode (standard Markdown, no transformation)
  - `off` / `"false"` / native boolean `false` — Obsidian-style relaxed breaks (apply `  \n` transformation)
  - `"auto"` — read `strictLineBreaks` from Obsidian's `app.json`
- Default: `"on"` (standard Markdown behavior, no transformation applied)
- Note: Obsidian itself defaults to relaxed breaks (strict OFF). Syntagmax defaults to strict ON for standard Markdown compatibility. Users wanting vault-consistent behavior should use `"auto"` or `"off"`.
- `auto` requires `integration = true` in `[drivers.obsidian]`; if not, raise a fatal configuration error
- When strict mode is OFF, single newlines in TextBlock content and artifact `contents` field are converted to `  \n` (two trailing spaces + newline) at extraction time
- When strict mode is ON (default), no transformation is applied
- The transformation must be code-block-aware, CRLF-safe, and block-syntax-aware
- New function in `obsidian_settings.py` to read `strictLineBreaks` from `app.json`

## Configuration

```toml
[drivers.obsidian]
strict_line_breaks = "off"      # "on" | "true" | "off" | "false" | "auto" | true | false
integration = true              # required for "auto"
```

- `strict_line_breaks` — controls line break interpretation (default: `"on"`)
- Accepts quoted strings (`"on"`, `"off"`, `"true"`, `"false"`, `"auto"`) or native TOML booleans (`true`, `false`)
- When `"auto"`, reads `strictLineBreaks` from `.obsidian/app.json` (requires `integration = true`)

## Obsidian Settings Source

The `auto` mode reads `app.json` from the Obsidian directory (`.obsidian` by default, or the configured `root`). The relevant field is `strictLineBreaks`:

```json
{
  "strictLineBreaks": true
}
```

- `true` → strict mode ON (no transformation)
- `false` → strict mode OFF (apply transformation)
- Key absent → default to `true` (Syntagmax's own default) with a warning logged

## Transformation Logic

When strict line breaks is OFF, single newlines are converted to Markdown hard breaks (two trailing spaces + newline):

**Input:**
```
Line one
Line two

Paragraph two
```

**Output:**
```
Line one  
Line two

Paragraph two
```

### Rules

1. Lines inside fenced code blocks (` ``` `) are never modified.
2. Lines consisting only of whitespace (empty lines or paragraph separators) are never modified.
3. Lines preceding an empty or whitespace-only line are never modified (to preserve paragraph breaks).
4. Markdown block-level elements are never modified: headings (starting with `#`), table rows (starting with `|`), list items (starting with `- `, `* `, `+ `, or numbered like `1. `), thematic breaks (`---`, `***`, `___`), and HTML blocks.
5. Already-existing hard breaks (trailing `  ` or `\`) are not doubled.
6. Any other line is appended with `  ` before its line ending (`\n` or `\r\n`), preserving the original line ending format.
7. The transformation is applied at extraction time, affecting both TextBlock content and artifact `contents` fields.

## Error Handling

- `strict_line_breaks = "auto"` with `integration = false` → fatal configuration error
- `auto` mode with missing/unreadable `app.json` → warning logged, defaults to strict ON (no transform)
- `auto` mode with `strictLineBreaks` key absent from `app.json` → warning logged, defaults to strict ON (no transform)

## Proposed Solution

1. Add `strict_line_breaks` field to `ObsidianDriverConfig` as `str | bool` with default `"on"`, accepting `on`/`true`/`off`/`false`/`auto` (strings) and native TOML booleans `true`/`false`. Normalizes value to lowercase string in validation.
2. Add config-time validation: if `strict_line_breaks = "auto"` but `integration = false`, raise `FatalError`
3. Add `read_obsidian_strict_line_breaks()` to `obsidian_settings.py`
4. Resolve the effective boolean in `Config` via `resolve_strict_line_breaks() -> bool` (eagerly for `on`/`off`/`true`/`false`, lazily for `auto`; cached)
5. Implement a code-block-aware, CRLF-safe, and block-syntax-aware line-break transformation function `apply_soft_line_breaks(text: str) -> str`
6. Apply transformation in `ObsidianExtractor.extract_blocks_from_file()` to both TextBlock content and artifact contents

## Task Breakdown

### Task 1: Add `strict_line_breaks` field to `ObsidianDriverConfig`

- **Objective:** Extend the config model to accept the new setting with proper validation, supporting both string and native TOML boolean values.
- **Implementation:** In `src/syntagmax/config.py`, add a `strict_line_breaks: str | bool` field to `ObsidianDriverConfig` with default `"on"`. Add a `@field_validator` that: (1) converts native booleans (`True` → `"true"`, `False` → `"false"`), (2) normalizes strings to lowercase, (3) validates against the allowed set `{"on", "true", "off", "false", "auto"}`. Store normalized lowercase string form.
- **Test:** Unit test that: valid string values parse correctly, native TOML booleans (`true`/`false`) parse correctly, invalid values raise `ValidationError`, and default is `"on"`.
- **Demo:** Both `strict_line_breaks = "off"` and `strict_line_breaks = false` load correctly and normalize to `"false"`/`"off"` respectively.

### Task 2: Add cross-field validation for `auto` + `integration`

- **Objective:** Raise a fatal configuration error when `strict_line_breaks = "auto"` but `integration = false`.
- **Implementation:** In `Config._read_config()`, after setting `self._obsidian_driver_config`, check if `strict_line_breaks == "auto"` and `integration == False`. If so, append an error message to the errors list (e.g., `'strict_line_breaks = "auto" requires integration = true in [drivers.obsidian]'`). This will be raised as a `FatalError`.
- **Test:** Unit test confirming `FatalError` is raised with appropriate message when `auto` is used without `integration = true`. Test that `auto` + `integration = true` passes validation (with a valid `app.json` present).
- **Demo:** Running with `strict_line_breaks = "auto"` and no `integration = true` produces a clear fatal error message.

### Task 3: Implement `read_obsidian_strict_line_breaks()` in `obsidian_settings.py`

- **Objective:** Read the `strictLineBreaks` boolean from Obsidian's `app.json`.
- **Implementation:** Add function `read_obsidian_strict_line_breaks(base_dir: Path, root_override: str | None = None) -> bool | None`. Same pattern as existing `read_obsidian_attachment_path`: resolve `.obsidian` dir, read `app.json`, extract `strictLineBreaks` key. Returns `True` if the key is truthy, `False` if present and falsy, `None` if key is missing or file unreadable (with warning). Reuse the same file-reading and error-handling pattern.
- **Test:** Tests covering: (a) `strictLineBreaks: true` returns `True`, (b) `strictLineBreaks: false` returns `False`, (c) key absent returns `None` with warning, (d) missing `app.json` returns `None`, (e) respects `root_override`.
- **Demo:** Calling the function on a mock `app.json` with `"strictLineBreaks": true` returns `True`.

### Task 4: Resolve effective strict-line-breaks mode in Config

- **Objective:** Provide a resolved boolean property on `Config` that the extractor can use.
- **Implementation:** Add a method `resolve_strict_line_breaks() -> bool` on `Config`. For `"on"`/`"true"` return `True`. For `"off"`/`"false"` return `False`. For `"auto"`, call `read_obsidian_strict_line_breaks(self._base_dir, self._obsidian_driver_config.root)` — if `None` is returned (key not found), default to `True` (matching Syntagmax's own default of strict mode ON) and log a warning. Cache the result.
- **Test:** Unit tests for each mode: `on`→`True`, `off`→`False`, `auto` with `strictLineBreaks: true` in app.json → `True`, `auto` with `strictLineBreaks: false` → `False`, `auto` with missing key → `True` (default) with warning.
- **Demo:** Config with `strict_line_breaks = "auto"` and a mock `app.json` containing `"strictLineBreaks": false` resolves to `False`.

### Task 5: Implement the line-break transformation function

- **Objective:** Create a code-block-aware, CRLF-safe, and block-syntax-aware function that converts single `\n` to `  \n` (Markdown hard break).
- **Implementation:** Add a utility function `apply_soft_line_breaks(text: str) -> str` in `src/syntagmax/extractors/markdown.py`. Logic:
  1. Split content by lines, preserving original line endings (`\r\n` or `\n`).
  2. Track fenced code block state (` ``` `); lines inside code blocks are passed through verbatim.
  3. For each non-code-block line, skip transformation if:
     - The line is empty or whitespace-only (paragraph separator).
     - The next line is empty or whitespace-only (line precedes a paragraph break).
     - The line is a Markdown block-level element: heading (`#`), table row (`|`), list item (`- `, `* `, `+ `, `1. `), thematic break (`---`, `***`, `___`), or HTML block (`<`).
     - The line already ends with a hard break (trailing `  ` or `\` before the line ending).
  4. For all other lines, append `  ` before the line ending, preserving the original ending format (`\r\n` or `\n`).
- **Test:** Tests: (a) single `\n` between text → `  \n`, (b) `\n\n` unchanged, (c) already-hard-break (`  \n`) unchanged, (d) content inside ` ``` ` blocks untouched, (e) empty string → empty string, (f) CRLF line endings preserved correctly (`\r\n` → `  \r\n`), (g) table rows/headings/list items not modified, (h) line before empty line not modified, (i) whitespace-only lines not modified.
- **Demo:** `"line1\nline2\n\nparagraph2"` → `"line1  \nline2\n\nparagraph2"`; `"line1\r\nline2\r\n"` → `"line1  \r\nline2  \r\n"`; `"| col |\ntext\n"` → `"| col |\ntext  \n"`.

### Task 6: Apply transformation in ObsidianExtractor at extraction time

- **Objective:** Wire the transformation into the extraction pipeline so both TextBlock content and artifact `contents` are transformed when strict line breaks is OFF.
- **Implementation:** Override `extract_blocks_from_file()` in `ObsidianExtractor` (currently just inherits from `MarkdownExtractor`). After calling `super().extract_blocks_from_file(filepath)`, if `self._config.resolve_strict_line_breaks()` is `False`:
  1. Iterate over blocks — for `TextBlock` instances, apply `apply_soft_line_breaks(block.content)` and replace content.
  2. For `ArtifactBlock` instances, apply `apply_soft_line_breaks()` to the artifact's `contents` field value (if present in `artifact.fields`).
- **Test:** Integration test with a mock Obsidian file containing single newlines, verifying: (a) with `strict_line_breaks = "off"`, extracted content has `  \n`; (b) with `strict_line_breaks = "on"` (default), content is unchanged; (c) code blocks within requirements are untouched.
- **Demo:** Extracting a file with `"Line one\nLine two"` in a text block produces `"Line one  \nLine two"` when strict_line_breaks is off.

### Task 7: Update documentation

- **Objective:** Document the new setting in configuration reference and README.
- **Implementation:**
  1. `docs/reference/configuration.md` — Add `strict_line_breaks` row to the `[drivers.obsidian]` table with type, default, and description. Add a subsection explaining behavior and accepted values.
  2. `README.md` — Mention the setting in the Obsidian section or add a sibling section.
- **Test:** Review docs for accuracy.
- **Demo:** A user reading the configuration reference can discover and configure `strict_line_breaks`.
