# Specification: Publishing Configuration System

## Problem Statement

The current `publish` command renders block trees using a hardcoded format. We need a configurable rendering system driven by per-input-record YAML files that control how artifacts and text blocks are formatted in the output document.

## Requirements

- Per-input-record YAML publish config (shared or overridden via `publish` field in `config.toml`)
- Default file: `.syntagmax/publish.yaml`; falls back to all-default rendering if absent
- Config controls: `start_level`, `remove_numeric_prefixes_in_headers`, `include_plain_text`, `ignore_plain_text_prefixes`, and `render` section
- `render` section maps artifact types and markers to rendering rules (table/text sections with attribute aliases)
- CLI: `syntagmax publish [RECORDS...] [--all] [--single] [--output <path-or-dir>] [-f <config-file>] [--date-suffix]`
- Output naming and compilation:
  - If `--single` is specified, compile all published records sequentially into a single file. In this case, `--output` represents a filename (default: `.syntagmax/reports/published.md`).
  - If `--single` is not specified, publish each record to a separate file. In this case, `--output` represents a directory (default: `.syntagmax/reports/`).
  - Filename naming for separate records: `<output_dir>/<INPUT_RECORD_NAME>.md` (no date by default).
  - The date suffix `_<YYYY-MM-DD>` is only appended to separate filenames (e.g. `<INPUT_RECORD_NAME>_<YYYY-MM-DD>.md`) if the optional `--date-suffix` CLI flag is provided.
- Fallback rendering for unmapped artifact types (heading + body + metadata table)
- JSON Schema derived from Pydantic model
- Update `example/publishing` to match new config format

## Background

- Current `publish.py` has `build_block_tree()` (builds from all records) and `render_block_tree()` (hardcoded format)
- `BlockTree` → `InputBlock` → `FileRecord` → `Block` (TextBlock/ArtifactBlock/ErrorBlock)
- `Artifact.fields` is `dict[str, str | list[str]]`; always has `id` and `contents`
- `TextBlock` has `content: str` and `marker: str | None`
- Existing example has a `publish.yaml` in `.config/` (old location) with the render structure already sketched
- PyYAML and Pydantic are already dependencies
- Jinja2 is available but the publish renderer currently uses string concatenation

## Configuration Model

### Publishing Configuration File Location

Publishing configuration is defined per input record as a YAML file, defaulting to `publish.yaml` in the `.syntagmax` directory.

If no filename is given and the file does not exist, assume all defaults.

Multiple input records can share a single publish config file.

#### Example (config.toml)

```toml
[[input]]
name = "system-requirements"
dir = "SYS"
driver = "obsidian"
atype = "SYS"
publish = "publish-sys-reqs.yaml"
```

### Publishing Configuration YAML Structure

```yaml
start_level: 1
render:
  REQ:
    - type: table
      attributes:
        - id:
            alias: "Identifier"
        - parent:
            alias: "Parent"
    - type: text
      mode: block
      attributes:
        - contents:
            alias: "Requirement"
  COM:
    - type: text
      mode: block
      alias: "Comment"
```

### Global Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `start_level` | int | Starting heading level in the output document (offset) | 1 |
| `remove_numeric_prefixes_in_headers` | bool | Strip numeric prefixes (matching regex `^\s*([0-9]+(\.[0-9]+)*\s*[-.]?|[0-9]+\s+)(.*)$`) | true |
| `include_plain_text` | bool | Include plain text (non-requirements) in the output | true |
| `ignore_plain_text_prefixes` | list[str] | Line prefixes to exclude from the output | [] |

### Render Section

The `render` section defines rendering parameters for artifact and non-artifact text blocks. Keys correspond to artifact types or block markers.

#### Artifact Render Configuration

Each artifact is rendered as a set of sections. Each section can be either `table` or `text`.

Every section definition shall have an `attributes` definition:

```yaml
render:
  <atype>:
    - type: text
      mode: block
      attributes:
        - id:
            alias: "Identifier"
        - parent:
            alias: "Parent"
```

- Attribute names (e.g., `id`, `parent`) shall be defined by the metamodel.
- Attribute lookup in the artifact fields is case-insensitive.
- `alias` is the name used in publication: for tables — a column name; for text sections — a caption.
- For text sections: `mode` field (enum: `block`, `inline`) defines whether output appears on a new line after the alias (`block`) or on the same line (`inline`).

##### Markdown Layout Rules:
- **Bolding**: Attribute and marker aliases must be wrapped in `**` (e.g. `**Alias**`).
- **Block Mode**:
  ```markdown
  **Alias**

  Value
  ```
- **Inline Mode**:
  `**Alias**: Value` on a single line.
- **Spacing**: A single blank line must be inserted between adjacent sections and blocks.

#### Non-Artifact Text Block Render Configuration

Text blocks with markers are rendered as text sections. For this version, the only section type supported is `text` in `block` and `inline` modes.

```yaml
render:
  COM:
    - type: text
      mode: block
      alias: "Comment"
```

### Fallback Rendering

If an artifact type or marker is encountered during publishing but has no entry in the `render` section, it is rendered with the default format:
- Heading with the artifact ID
- Body text (contents)
- Metadata table (field/value for all fields except `id` and `contents`)

## CLI Interface

### Syntax

```bash
uv run syntagmax publish [RECORDS...] [--all] [--single] [--output <path-or-dir>] [-f <config-file>] [--date-suffix]
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `RECORDS` | No* | One or more input record names to publish |
| `--all` | No* | Publish all input records |
| `--single` | No | Compile all published records sequentially into a single file |
| `--output <path-or-dir>` | No | Output directory or file path. Defaults to `.syntagmax/reports/` (if separate files) or `.syntagmax/reports/published.md` (if `--single`). |
| `-f, --config-file` | No | Path to config file (default: `.syntagmax/config.toml`) |
| `--date-suffix` | No | Append date suffix `_<YYYY-MM-DD>` to output filenames (only valid when publishing separate files, i.e., without `--single`). |

*Either `RECORDS` or `--all` must be provided.

### Output

- If `--single` is active:
  Writes a single compiled markdown file to the path specified in `--output`.
- If `--single` is not active:
  Writes separate markdown files for each input record:
  - Default: `<output_dir>/<INPUT_RECORD_NAME>.md`
  - With `--date-suffix`: `<output_dir>/<INPUT_RECORD_NAME>_<YYYY-MM-DD>.md`

### Error Handling

- Error if neither records nor `--all` is provided.
- Error if a named record doesn't exist in the project config.
- Error if `--date-suffix` is provided in combination with `--single`.

## Proposed Solution

### Architecture

1. New module `src/syntagmax/publish_config.py` — Pydantic models for the YAML schema
2. Extended `InputConfig` / `InputRecord` with optional `publish` field
3. Config-aware renderer in `publish.py` applying render rules per block type
4. Reworked CLI accepting record names or `--all`
5. JSON Schema generated from Pydantic model via `PublishConfig.model_json_schema()`

## Task Breakdown

### Task 1: Define the PublishConfig Pydantic model

- Create `src/syntagmax/publish_config.py` with Pydantic models representing the publish YAML schema.
- Models:
  - `AttributeRender`: `alias: str`
  - `TableSection`: `type: Literal['table']`, `attributes: list[dict[str, AttributeRender]]` (validator enforces each dict in the list contains exactly one key)
  - `TextSection`: `type: Literal['text']`, `mode: Literal['block', 'inline']`, `attributes: list[dict[str, AttributeRender]]` (validator enforces each dict contains exactly one key; enforces `alias` field is absent)
  - `MarkerRenderSection`: `type: Literal['text']`, `mode: Literal['block', 'inline']`, `alias: str` (enforces `attributes` field is absent)
  - `PublishConfig`: `start_level: int = 1`, `remove_numeric_prefixes_in_headers: bool = True`, `include_plain_text: bool = True`, `ignore_plain_text_prefixes: list[str] = []`, `render: dict[str, list[Union[TableSection, TextSection, MarkerRenderSection]]]`
- Add a `load_publish_config(path: Path | None, root_dir: Path) -> PublishConfig` function that loads YAML or returns defaults.
- Test: Unit tests verifying model validation with valid/invalid YAML inputs, default values, and discriminated union parsing of section types.
- Demo: `uv run pytest tests/test_publish_config.py` passes.

### Task 2: Add `publish` field to InputConfig and wire config loading

- Extend `InputConfig` with an optional `publish: str | None` field.
- Add `publish_config: str | None` to `InputRecord` dataclass.
- In `Config._read_input_records()`, propagate the `publish` field to `InputRecord`.
- Add a method `Config.load_publish_config(record: InputRecord) -> PublishConfig` that resolves: record-specific path → default `.syntagmax/publish.yaml` → all defaults.
- Test: Unit test with config.toml having `publish = "custom.yaml"` and one without; verify correct resolution.
- Demo: `uv run pytest tests/test_publish_config.py` passes with config resolution tests.

### Task 3: Implement the config-driven block renderer

- Rewrite `render_block_tree()` (or create a new `render_input_block()`) to apply `PublishConfig` rendering rules.
- For artifacts: look up `render[artifact.atype]`; if found, render sections in order (table/text); if not found, use default format (heading + body + field/value table).
- For text blocks with markers: look up `render[marker]`; apply text rendering with alias.
- For plain text blocks: respect `include_plain_text` and `ignore_plain_text_prefixes`.
- Apply `start_level` offset to all headings in text blocks and artifact headings.
- Apply `remove_numeric_prefixes_in_headers` to strip leading numeric prefixes from headings.
- Output one markdown string per input block.
- Test: Unit tests with mock block trees and various publish configs, verifying correct table rendering, text inline/block modes, heading level adjustment, prefix stripping, and plain text filtering.
- Demo: `uv run pytest tests/test_publish.py` passes with all rendering scenarios.

### Task 4: Rework the CLI `publish` command

- Change the CLI to accept record names or `--all`, with `--single` support, and `--output` representing either a file path or directory.
- New signature: `syntagmax publish [RECORDS...] [--all] [--single] [--output <path-or-dir>] [-f <config-file>] [--date-suffix]`
- Validation:
  - Error if neither records nor `--all` provided.
  - Error if a named record doesn't exist.
  - Error if `--date-suffix` is provided in combination with `--single`.
- Execution:
  - If `--single` is active: load publish config for all records (or use default if they differ), build block tree combining all selected records, render them sequentially separated by a blank line, and write to a single file at `--output`.
  - If `--single` is not active: for each selected record, load its publish config, build the block tree for that record only, render, and write to `<output_dir>/<RECORD_NAME>.md` (or `<output_dir>/<RECORD_NAME>_<YYYY-MM-DD>.md` if `--date-suffix` is set).
- Print summary with file paths and statistics (number of artifacts, text blocks).
- Test: Integration test using a temp project, verify file naming, `--single` compilation, and content.
- Demo: `uv run syntagmax --cwd ./example/publishing publish --all` produces output files.

### Task 5: Update the publishing example

- Move/rename `.config/publish.yaml` → `.syntagmax/publish.yaml` and update its content (change `separate` → `block`, remove `requirement` section, align with the new schema).
- Add `publish` field to `config.toml` if a non-default path is needed (or rely on default).
- Regenerate the example output to match the new format.
- Remove the old `.config/` directory if no longer needed.
- Test: `uv run syntagmax --cwd ./example/publishing publish --all` produces valid output matching expectations.
- Demo: Example output is up-to-date and serves as documentation.

### Task 6: Generate JSON Schema from the Pydantic model

- Add a CLI sub-command (`syntagmax schema publish`) that prints/writes the JSON Schema derived from `PublishConfig.model_json_schema()`.
- Place the generated schema at `docs/schemas/publish-config.schema.json`.
- Test: Validate the example `publish.yaml` against the generated schema (load YAML and validate with `PublishConfig`).
- Demo: `uv run syntagmax schema publish` outputs valid JSON Schema; example config passes validation.

## Non-Functional Requirements

- **Determinism**: Identical source structures and configurations must produce bit-for-bit identical outputs.
- **Input Immutability**: The publishing process must never alter source project files.
- **Logging**: Log execution metadata including timestamp, target section name, options, statistics, and any warnings/errors.
