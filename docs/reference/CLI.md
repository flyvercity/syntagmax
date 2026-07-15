# CLI Reference

Complete reference for the `syntagmax` command-line interface.

## Entry Point

```
syntagmax [OPTIONS] COMMAND [ARGS]...
```

The CLI is invoked as `syntagmax`. All commands share a set of global options that must appear **before** the command name.

## Global Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--verbose` | Flag | off | Enable verbose (DEBUG-level) logging |
| `--render-tree` | Flag | off | Include the artifact tree in the analysis report |
| `--cwd PATH` | Path | current dir | Change the working directory before executing |
| `--no-git` | Flag | off | Skip git history extraction |
| `--output PATH` | String | `.syntagmax/reports/report.md` | Report output file path (use `console` for stdout) |
| `--version` | Flag | — | Show version and exit |
| `--help` | Flag | — | Show help and exit |

### Examples

```bash
# Run with verbose logging
syntagmax --verbose analyze

# Change working directory and render tree
syntagmax --render-tree --cwd ./my-project analyze

# Skip git integration for faster analysis
syntagmax --no-git analyze

# Output report to stdout
syntagmax --output console --render-tree analyze
```

---

## Commands

### `init`

Initialise a new Syntagmax project in the current (or `--cwd`) directory.

```
syntagmax init
```

Creates a `.syntagmax/` directory containing:
- `config.toml` — template configuration file
- `project.syntagmax` — basic metamodel definition

**No additional options or arguments.**

#### Example

```bash
syntagmax init
syntagmax --cwd ./new-project init
```

---

### `analyze`

Run the analysis pipeline on the project.

```
syntagmax analyze [OPTIONS] [STEP]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `STEP` | No | `metrics` | Target analysis step. Syntagmax resolves and executes all dependencies automatically. |

Available steps (in dependency order):

| Step | Description |
|------|-------------|
| `extract` | Extract artifacts from source files |
| `tree` | Build and validate the artifact tree |
| `impact` | Perform impact analysis (requires git history) |
| `metrics` | Calculate project metrics and coverage |
| `ai` | Perform AI-assisted analysis |

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-f, --config-file PATH` | Path | `.syntagmax/config.toml` | Path to the project configuration file |
| `--allow-dirty-worktree` | Flag | off | Allow analysis on a dirty git worktree |
| `--suppress-tracing` | Flag | off | Suppress tracing model errors |

#### Examples

```bash
# Run full analysis (up to metrics) with default config
syntagmax analyze

# Run only extraction
syntagmax analyze extract

# Run impact analysis with a custom config file
syntagmax analyze -f custom-config.toml impact

# Run AI analysis, allow dirty worktree
syntagmax analyze --allow-dirty-worktree ai

# Suppress tracing errors during tree validation
syntagmax analyze --suppress-tracing tree

# Combine with global options
syntagmax --render-tree --output console analyze
```

---

### `publish`

Publish project inputs to structured Markdown documents, with optional DOCX/PDF export via Pandoc.

```
syntagmax publish [OPTIONS] [RECORDS...]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `RECORDS` | No* | Names of input records to publish. *Required unless `--all` is specified. |

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--all` | Flag | off | Publish all input records defined in config |
| `--single` | Flag | off | Compile all selected records into a single file |
| `--output PATH` | Path | `.syntagmax/reports/` (multi) or `.syntagmax/reports/published.md` (single) | Output directory (multi-file) or file path (single) |
| `-f, --config-file PATH` | Path | `.syntagmax/config.toml` | Path to the project configuration file |
| `--date-suffix` | Flag | off | Append date suffix (`YYYY-MM-DD`) to filenames. Cannot be combined with `--single`. |
| `--docx` | Flag | off | Convert output to DOCX via Pandoc |
| `--pdf` | Flag | off | Convert output to PDF via Pandoc |
| `--docx-template PATH` | String | from `publish.yaml` | Override DOCX reference template path. Use `"none"` to disable. |
| `--pre-filter NAME` | String | — | Run a named pre-publishing block filter plugin |

#### Examples

```bash
# Publish all records to separate files
syntagmax publish --all

# Publish specific records
syntagmax publish requirements system-requirements

# Single consolidated document
syntagmax publish --all --single

# Publish with DOCX and PDF export
syntagmax publish --all --single --docx --pdf

# Custom output path with date suffix
syntagmax publish --all --output ./reports/ --date-suffix

# Use a custom DOCX template
syntagmax publish --all --single --docx --docx-template ./templates/ref.docx

# Disable DOCX template
syntagmax publish --all --single --docx --docx-template none

# Pre-filter blocks via plugin before publishing
syntagmax publish --all --pre-filter my-filter-plugin

# Custom config file
syntagmax publish --all -f ./custom/config.toml
```

---

### `trace`

Export traceability matrix as CSV or TSV.

```
syntagmax trace [OPTIONS]
```

Uses left outer join semantics — every lead artifact appears even if it has no links to the target type.

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--child TYPE` | String | **required** | Artifact type of the child (e.g., `REQ`) |
| `--parent TYPE` | String | **required** | Artifact type of the parent (e.g., `SYS`) |
| `--forward / --reverse` | Flag pair | `--forward` | Direction: forward (child→parent) or reverse (parent→child) |
| `--attribute NAME` | String (repeatable) | — | Additional lead artifact attributes to include as columns |
| `--flat` | Flag | off | Combine multiple linked IDs into semicolon-separated values |
| `--delimiter CHAR` | String | `,` (auto `\t` for `.tsv`) | Column delimiter |
| `--plugin NAME` | String | — | Delegate export to a named plugin |
| `--output PATH` | String | `.syntagmax/reports/trace.csv` | Output file path. Use `console` for stdout. |
| `-f, --config-file PATH` | Path | `.syntagmax/config.toml` | Path to the project configuration file |

#### Forward vs Reverse

- **Forward** (default): Lead artifacts are children. Each row shows a child ID and its linked parent ID(s).
- **Reverse**: Lead artifacts are parents. Each row shows a parent ID and its linked child ID(s).

#### Flat Mode

Without `--flat`, a child with multiple parents produces one row per link. With `--flat`, all linked IDs are combined into a single semicolon-separated cell.

#### Examples

```bash
# Forward matrix (REQ → SYS) as CSV
syntagmax trace --child REQ --parent SYS

# Reverse matrix with extra attributes
syntagmax trace --child REQ --parent SYS --reverse --attribute title --attribute status

# Flat mode, TSV output (delimiter auto-detected from extension)
syntagmax trace --child REQ --parent SYS --flat --output .syntagmax/reports/trace.tsv

# Explicit tab delimiter
syntagmax trace --child REQ --parent SYS --delimiter '\t'

# Export to stdout
syntagmax trace --child REQ --parent SYS --output console

# Use a plugin for custom export
syntagmax trace --child REQ --parent SYS --plugin tsv-export

# Custom config
syntagmax trace --child REQ --parent SYS -f ./custom/config.toml
```


### `change`

Change analysis commands group.

```
syntagmax change COMMAND [OPTIONS]
```

#### Subcommands

- [`report`](#change-report) — Generate change report between two revisions

---

### `change report`

Generate a change report comparing artifacts between two Git revisions.

```
syntagmax change report [OPTIONS]
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--base REV` | String | **required** | Base Git revision (commit, tag, branch, HEAD, HEAD~N, or `working`) |
| `--target REV` | String | **required** | Target Git revision |
| `--output PATH` | String | `.syntagmax/reports/change/` | Output directory or `console` for stdout |
| `--include-non-artifact` | Flag | off | Include non-artifact text block changes |
| `--single` | Flag | off | Generate a single consolidated report across all input records |
| `--summary` | Flag | off | Generate abbreviated summary report (no content or attribute diffs) |
| `-f, --config-file PATH` | Path | `.syntagmax/config.toml` | Path to config file |

#### Summary Mode

When `--summary` is active, the report contains only:

- Repository information (base/target revision, timestamp, record name)
- Summary statistics table (files changed, artifacts added/modified/removed)
- Per-file breakdown listing changed objects by ID and text fragment line ranges

The following are omitted: object text content, attribute change tables, link changes, text fragment content, Previous/Current comparison blocks, and fallback plain-text diffs.

Summary reports use the filename suffix `-summary` (e.g. `requirements-abc1234-to-def5678-20260715-summary.md`).

#### Binary/Sidecar Artifacts

Sidecar-managed binary artifacts (images, diagrams) are automatically included in change reports. For each sidecar artifact, the report shows:

- SHA-256 hash comparison of the primary binary file
- File size at both revisions
- Pixel dimensions (when the optional `Pillow` dependency is installed via `pip install syntagmax[images]`)
- Sidecar metadata (YAML attribute) changes

The binary content property table is only rendered when the file content actually changed. Metadata-only changes (sidecar YAML edits without binary modification) show only the attribute changes table.

#### Output Filenames

- Per-record: `<section>-<base_rev>-to-<target_rev>-<YYYYMMDD>.md`
- Consolidated (`--single`): `change-<base_rev>-to-<target_rev>-<YYYYMMDD>.md`
- Summary variants append `-summary` before `.md`

#### Examples

```bash
# Compare last commit against current HEAD
syntagmax change report --base HEAD~1 --target HEAD

# Compare two tags
syntagmax change report --base v1.2.0 --target v1.3.0

# Quick summary overview
syntagmax change report --summary --base v1.2.0 --target v1.3.0

# Summary to stdout
syntagmax change report --summary --base HEAD~1 --target HEAD --output console

# Include text block changes in summary
syntagmax change report --summary --include-non-artifact --base HEAD~1 --target HEAD

# Single consolidated report
syntagmax change report --single --base release --target develop

# Compare against uncommitted working directory changes
syntagmax change report --base HEAD --target working
```

---


---

### `edit`

Project editing commands group.

```
syntagmax edit COMMAND [OPTIONS]
```

#### Subcommands

- [`renumber`](#edit-renumber) — Renumber artifact IDs
- [`attrs`](#edit-attrs) — Bulk attribute manipulation
- [`markers`](#edit-markers) — Fragment marker management

---

### `edit renumber`

Renumber artifact IDs according to a schema.

```
syntagmax edit renumber [OPTIONS] [CONFIG_PATH]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONFIG_PATH` | No | `.syntagmax/config.toml` | Path to the project configuration file |

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--all` | Flag | off | Renumber all artifacts. Either `--all` or `--atype` is required. |
| `--atype TYPE` | String | — | Renumber only artifacts of the specified type |
| `--schema SCHEMA` | String | from config | Custom ID schema (see schema format below) |
| `--dry-run` | Flag | off | Preview changes without modifying files |

#### ID Schema Format

The schema string supports the following macros:

| Macro | Description |
|-------|-------------|
| `{atype}` | Artifact type (e.g., `REQ`, `SYS`) |
| `{num}` | Sequential number |
| `{num:N}` | Zero-padded sequential number (e.g., `{num:3}` → `001`) |

#### Examples

```bash
# Renumber all artifacts with default schema
syntagmax edit renumber --all

# Renumber only REQ artifacts
syntagmax edit renumber --atype REQ

# Custom schema with zero-padding
syntagmax edit renumber --all --schema 'myproject-{atype}-{num:4}'

# Dry run to preview changes
syntagmax edit renumber --all --dry-run

# Specify a custom config path
syntagmax edit renumber --all ./custom/config.toml
```

---

### `edit attrs`

Add, remove, or replace attributes on artifacts in bulk. Only the Obsidian driver is supported.

```
syntagmax edit attrs [OPTIONS]
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-f, --config-file PATH` | Path | `.syntagmax/config.toml` | Path to the project configuration file |
| `-o, --operation` | Choice: `add`, `del`, `replace` | `add` | Operation to perform |
| `-t, --type` | Choice: `attr`, `field` | `attr` | Target: `attr` (YAML frontmatter) or `field` (inline `[FIELD]`) |
| `-n, --name NAME` | String | — | Attribute name. Omit for `add` to add all mandatory metamodel attributes. |
| `-l, --value VALUE` | String | `TBD` (for add) | Attribute value |
| `-s, --section NAME` | String | **required** | Input record name to operate on |
| `--csv PATH` | Path | — | CSV file for per-artifact value lookup |
| `--csv-id-column NAME` | String | `id` | CSV column for artifact ID matching |
| `--csv-value-column NAME` | String | `value` | CSV column for attribute value |
| `-d, --csv-delimiter CHAR` | String | `,` | CSV column delimiter |
| `--dry-run` | Flag | off | Preview changes without modifying files |

#### Operation Behaviour

| Operation | Behaviour |
|-----------|-----------|
| `add` | Adds the attribute to artifacts that do not already have it. Uses `TBD` as default value. |
| `del` | Removes the attribute wherever it exists; no-op otherwise. |
| `replace` | Updates existing values in place (preserving field position); appends if missing. |

#### Validation Rules

- `--name` is **required** for `del` and `replace` operations.
- `--value` or `--csv` is **required** for `replace`.
- Cannot specify `--value` without `--name` for metamodel-driven add.

#### CSV Mapping

When `--csv` is provided, values are looked up per artifact:
- The `--csv-id-column` is matched against artifact IDs.
- The `--csv-value-column` provides the replacement value.
- `--value` serves as a fallback for unmatched IDs.

#### Examples

```bash
# Add all missing mandatory attributes (from metamodel) with TBD
syntagmax edit attrs -s software-requirements --dry-run

# Add 'owner' attribute with TBD to all artifacts in a section
syntagmax edit attrs -s system-requirements -n owner

# Add with a specific value
syntagmax edit attrs -s requirements -n status -l draft

# Replace attribute value across a section
syntagmax edit attrs -s requirements -o replace -n status -l active

# Remove an attribute
syntagmax edit attrs -s system-requirements -o del -n verified

# Import values from a CSV file
syntagmax edit attrs -s requirements -o replace -n doors_id \
  --csv mapping.csv --csv-id-column ext_id --csv-value-column doors_id -l UNKNOWN

# Operate on inline fields instead of YAML attributes
syntagmax edit attrs -s requirements -o add -t field -n PRIORITY -l HIGH

# Use a custom config and preview
syntagmax edit attrs -f custom-config.toml -s reqs -o replace -n status -l active --dry-run
```

---

### `edit markers`

Fragment marker management commands group.

```
syntagmax edit markers COMMAND [OPTIONS]
```

#### Subcommands

- [`renumber`](#edit-markers-renumber) — Assign sequential numeric IDs to unmarked fragment blocks

---

### `edit markers renumber`

Assign sequential numeric IDs to non-artifact marked text blocks (e.g., `[COM]`, `[NOTE]`) that don't already have explicit IDs. Numbering is independent per marker type and starts from `max_existing + 1` (or 1 if none exist).

```
syntagmax edit markers renumber [OPTIONS] [CONFIG_PATH]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONFIG_PATH` | No | `.syntagmax/config.toml` | Path to the project configuration file |

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--all` | Flag | off | Renumber across all input records. Either `--all` or `--section` is required. |
| `--section NAME` | String | — | Restrict renumbering to a specific input record |
| `--marker NAME` | String | — | Only renumber blocks of a specific marker type |
| `--dry-run` | Flag | off | Show planned changes without modifying files |

#### Behaviour

- Only input records using the Obsidian driver with configured `markers` are processed.
- Existing explicit IDs (numeric or non-numeric) are never modified.
- New IDs are plain integers written into the opening tag: `[COM]` → `[COM 3]`.
- The original casing of the marker name is preserved: `[com]` → `[com 3]`.
- The closing tag `[/MARKER]` is never modified.
- All three marker formats (closed paired, unclosed paired, line-prefix) are supported.
- Files are written with Unix-style line endings (LF).
- ID numbering is shared across files within the targeted records (global max per marker type).

#### Examples

```bash
# Renumber all unmarked blocks across the project
syntagmax edit markers renumber --all

# Dry-run to preview changes
syntagmax edit markers renumber --all --dry-run

# Only renumber COM markers in a specific section
syntagmax edit markers renumber --section system-requirements --marker COM

# Using a custom config path
syntagmax edit markers renumber --all .syntagmax/config.toml
```

---

### `mcp`

MCP server management commands group.

```
syntagmax mcp COMMAND [OPTIONS]
```

#### Subcommands

- [`run`](#mcp-run) — Start the MCP server

---

### `mcp run`

Start the Model Context Protocol (MCP) server.

```
syntagmax mcp run [OPTIONS] CONFIG_PATH
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `CONFIG_PATH` | Yes | Path to the project configuration file |

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--host HOST` | String | `127.0.0.1` | Host address for SSE transport |
| `--port PORT` | Integer | `8000` | Port for SSE transport |
| `--sse-path PATH` | String | `/` | URL path for the SSE stream |
| `--transport` | Choice: `stdio`, `sse` | `stdio` | MCP transport to use |

#### MCP Tools

The server exposes:
- `list_artifacts` — List all artifacts in the system
- `search_artifacts` — Search requirements by keyword
- `get_artifact_content` — Fetch full details of a specific requirement (including traceability)

#### Examples

```bash
# Start with stdio transport (default, for local MCP clients)
syntagmax mcp run .syntagmax/config.toml

# Start with SSE transport on custom port
syntagmax mcp run .syntagmax/config.toml --transport sse --port 9000

# Custom host and path
syntagmax mcp run .syntagmax/config.toml --transport sse --host 0.0.0.0 --port 8080 --sse-path /mcp
```

#### Client Configuration

For MCP clients supporting SSE:

```json
{
  "mcpServers": {
    "syntagmax": {
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

---

### `schema`

Schema generation commands group.

```
syntagmax schema COMMAND
```

#### Subcommands

- [`publish`](#schema-publish) — Generate JSON Schema for publishing configuration
- [`config`](#schema-config) — Generate JSON Schema for project configuration

---

### `schema publish`

Generate and print the JSON Schema for the publishing configuration (`publish.yaml`).

```
syntagmax schema publish
```

**No options.** Outputs JSON to stdout.

#### Example

```bash
# Print schema to stdout
syntagmax schema publish

# Save to file
syntagmax schema publish > publish-schema.json
```

---

### `schema config`

Generate and print the JSON Schema for the main project configuration (`config.toml`).

```
syntagmax schema config
```

**No options.** Outputs JSON to stdout.

#### Example

```bash
# Print schema to stdout
syntagmax schema config

# Save to file
syntagmax schema config > config-schema.json
```

---

## Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Success |
| 1 | Fatal error (configuration parse failure, missing required files) |
| 2 | RMS processing error |
| 3 | Unexpected error |

---

## Environment

- **Python**: Requires Python 3.13+
- **Pandoc**: Required for `--docx` and `--pdf` conversion (must be in PATH)
- **Git**: Required unless `--no-git` is used
- **Working directory**: Commands operate relative to the current directory or the path set via `--cwd`
- **Configuration**: Default config path is `.syntagmax/config.toml` for all commands

---

## Command Tree

```
syntagmax
├── init
├── analyze [STEP]
├── publish [RECORDS...]
├── trace
├── change
│   └── report
├── edit
│   ├── renumber [CONFIG_PATH]
│   ├── attrs
│   └── markers
│       └── renumber [CONFIG_PATH]
├── mcp
│   └── run CONFIG_PATH
└── schema
    ├── publish
    └── config
```
