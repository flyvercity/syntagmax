# Publishing Reference

Syntagmax can combine all project inputs into a single structured markdown document, preserving both artifact content and surrounding non-artifact text (headings, rationale, design notes, etc.).

## Command

```bash
syntagmax publish [RECORDS...] [--all] [--single] [--output <path-or-dir>] [-f <config-file>] [--date-suffix]
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `RECORDS` | No* | One or more input record names to publish |
| `--all` | No* | Publish all input records |
| `--single` | No | Compile all published records sequentially into a single file |
| `--output <path-or-dir>` | No | Output directory or file path. Defaults to `.syntagmax/reports/` (separate files) or `.syntagmax/reports/published.md` (`--single`). |
| `-f, --config-file` | No | Path to config file (default: `.syntagmax/config.toml`) |
| `--date-suffix` | No | Append `_<YYYY-MM-DD>` to output filenames (only valid without `--single`) |
| `--docx` | No | Convert output to DOCX via Pandoc |
| `--pdf` | No | Convert output to PDF via Pandoc |
| `--docx-template <path>` | No | Custom DOCX reference template (or `none` to disable) |

*Either `RECORDS` or `--all` must be provided.

### Behaviour

The publish command:
- Processes all input records from the project config
- Preserves non-artifact text blocks (context, rationale, notes) alongside requirements
- Renders each artifact in a normalised format: heading + body + metadata table
- Sorts files within each input record lexicographically by relative path

### Output Modes

- **Separate files** (default): Each record produces `<output_dir>/<RECORD_NAME>.md`
  - With `--date-suffix`: `<output_dir>/<RECORD_NAME>_<YYYY-MM-DD>.md`
- **Single file** (`--single`): All records compiled sequentially into one file at `--output`

### Examples

```bash
# Publish all records to separate files
syntagmax publish --all

# Publish specific records
syntagmax publish system-requirements software-requirements

# Single consolidated document
syntagmax publish --all --single --output ./reports/full-document.md

# With date suffix
syntagmax publish --all --date-suffix --output ./reports/
```

## DOCX/PDF Export (Pandoc Integration)

The `publish` command can optionally convert the generated Markdown to DOCX and/or PDF using [Pandoc](https://pandoc.org/).

```bash
# Publish all records and convert to Word
syntagmax publish --all --docx

# Publish consolidated document as PDF
syntagmax publish --all --single --pdf

# Produce both DOCX and PDF alongside Markdown
syntagmax publish --all --docx --pdf --output ./reports/

# Use a custom DOCX template (one-off override)
syntagmax publish --all --docx --docx-template ./templates/corporate.dotm

# Export without any template styling
syntagmax publish --all --docx --docx-template none
```

### Requirements

- Pandoc must be installed and available in your `PATH`.
- For PDF output, a LaTeX engine (e.g., `xelatex`, `pdflatex`) must also be installed.

### Behaviour

- The Markdown file is always generated first, regardless of conversion success.
- DOCX/PDF files are placed alongside the Markdown with the same base name (e.g., `rec1.md` → `rec1.docx`).
- If Pandoc is not found or conversion fails, a warning is logged with the exit status, the Markdown file is preserved, and the command exits successfully.

## publish.yaml Reference

Publishing configuration controls how artifacts and text blocks are rendered in the output document. It is defined as a YAML file, resolved in the following order:

1. Per-record `publish` field in `config.toml`
2. `publish.yaml` in the project root directory
3. `.syntagmax/publish.yaml`
4. All-default rendering (if no file exists)

### Linking a Custom Publish Config

```toml
[[input]]
name = "system-requirements"
dir = "SYS"
driver = "obsidian"
atype = "SYS"
publish = "publish-sys-reqs.yaml"
```

### Full Schema

```yaml
start_level: 1
remove_numeric_prefixes_in_headers: true
include_plain_text: true
ignore_plain_text_prefixes: []

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

docx-template:
  default-template: "templates/corporate.dotm"
  overrides:
    system-requirements: "templates/sys-template.dotm"
    implementation: "none"
```

### Global Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_level` | int | `1` | Starting heading level offset in the output document |
| `remove_numeric_prefixes_in_headers` | bool | `true` | Strip leading numeric prefixes (e.g., `1.2.3 Title` → `Title`) |
| `include_plain_text` | bool | `true` | Include plain (non-artifact) text in the output |
| `ignore_plain_text_prefixes` | list[str] | `[]` | Line prefixes to exclude from plain text output |

### Render Section

The `render` section maps artifact types and block markers to rendering rules. Keys correspond to artifact types (e.g., `REQ`, `SYS`) or fragment markers (e.g., `COM`, `NOTE`).

#### Artifact Render Configuration

Each artifact type is rendered as an ordered list of sections. Each section is either `table` or `text`:

```yaml
render:
  REQ:
    - type: table
      attributes:
        - id:
            alias: "Identifier"
        - parent:
            alias: "Parent Requirement"
    - type: text
      mode: block
      attributes:
        - contents:
            alias: "Requirement Text"
```

**Section types:**

| Type | Description |
|------|-------------|
| `table` | Renders attributes as a table (attribute aliases as column headers) |
| `text` | Renders attributes as formatted text with aliases as captions |

**Text mode:**

| Mode | Layout |
|------|--------|
| `block` | `**Alias**` on one line, value on the next (separated by blank line) |
| `inline` | `**Alias**: Value` on a single line |

**Attribute definitions:**
- Attribute names must match metamodel fields (case-insensitive lookup).
- `alias` specifies the display name (column header for tables, caption for text).

#### Marker Render Configuration

Text blocks with markers use a simplified text section:

```yaml
render:
  COM:
    - type: text
      mode: block
      alias: "Comment"
```

#### Fallback Rendering

Artifact types or markers without a `render` entry use the default format:
- Heading with the artifact ID
- Body text (contents)
- Metadata table (field/value for all fields except `id` and `contents`)

#### Markdown Layout Rules

- Attribute and marker aliases are wrapped in bold: `**Alias**`
- Block mode: `**Alias**\n\nValue`
- Inline mode: `**Alias**: Value`
- A single blank line separates adjacent sections and blocks

### DOCX Template Configuration

By default, Syntagmax applies a bundled reference document (`template.dotm`) when converting to DOCX via Pandoc's `--reference-doc` flag. This controls styles, headers, footers, and page layout in the output.

Templates are configured in the `docx-template` section of `publish.yaml`:

```yaml
docx-template:
  default-template: "templates/corporate.dotm"
  overrides:
    system-requirements: "templates/sys-template.dotm"
    implementation: "none"
```

| Field | Description |
|-------|-------------|
| `default-template` | Path to the default template (relative to the config directory), or `"none"` to disable |
| `overrides` | Per-record template overrides (record name → path or `"none"`) |

**Resolution order:**

1. `--docx-template` CLI option (overrides everything)
2. Per-record override in `docx-template.overrides.<record_name>`
3. `docx-template.default-template`
4. Bundled `template.dotm` (if no configuration is specified)

Setting a template value to `"none"` at any level disables the reference document for that record, producing a plain Pandoc conversion without styling.

## Error Handling

- Error if neither records nor `--all` is provided.
- Error if a named record does not exist in the project config.
- Error if `--date-suffix` is combined with `--single`.
