# Syntagmax - Git-Based Requirements Management System

Fully git-friendly lightweight requirements management system with tracing model verification, change detection, and propagation.

## Quick Demo (Development Environment)

Run example analysis with:

```bash
uv run syntagmax --render-tree --cwd ./example/obsidian-driver/ analyze
```

Run example publishing with:

```bash
uv run syntagmax --cwd ./example/obsidian-driver publish .syntagmax/reports/output.md
```

Run example tracing export with:

```bash
uv run syntagmax --cwd ./example/obsidian-driver trace --child REQ --parent SYS
```

## Getting Started

To initialize a new Syntagmax project in the current directory:

```bash
syntagmax init
```

This command creates a `.syntagmax` directory with:
- `config.toml`: A template configuration file with common options.
- `project.syntagmax`: A basic metamodel definition to get you started.

## Configuration

Syntagmax uses a TOML configuration file (default `.syntagmax/config.toml`). Key sections include:

- `[[input]]` — input source definitions (driver, artifact type, filters)
- `[metrics]` — metrics collection settings
- `[impact]` — impact analysis settings
- `[metamodel]` — metamodel file path
- `[ai]` — AI provider and model settings

```toml
base = ".."

[[input]]
name = "requirements"
dir = "requirements/REQS"
driver = "obsidian"

[metrics]
enabled = true

[metamodel]
filename = "project.syntagmax"

[ai]
provider = "anthropic"
model = "claude-sonnet-4-6"
```

For the full schema, input source options, marked fragments, and AI provider settings, see [docs/reference/configuration.md](docs/reference/configuration.md).

## Git Integration

Syntagmax automatically extracts revision history for each artifact using Git. This provides traceability and helps track changes over time.

### Revision Descriptors

Each artifact is attached with a set of revisions. A revision includes:
- **Short Hash**: The 7-character commit hash.
- **Timestamp**: Date and time of the commit.
- **Author**: Email of the commit author.

### Extraction Logic

- **Text-based artifacts** (e.g., source code sections, Obsidian requirements): Syntagmax uses `git blame` to identify all commits that affected the specific lines where the artifact is defined.
- **Sidecar artifacts**: Syntagmax identifies the last commit that affected the primary file (e.g., an image) and all commits that affected the sidecar metadata file.

### Disabling Git Integration

If you want to skip git history extraction (e.g., if you are not in a git repository or want to speed up analysis), use the `--no-git` flag:

```bash
syntagmax analyze .syntagmax/config.toml --no-git
```

## Running Analysis

The `analyze` command is the primary way to process your project. It supports a dynamic execution pipeline where you can request a specific target step.

```bash
syntagmax analyze [CONFIG_FILE] [STEP]
```

### Target Steps

Syntagmax will automatically resolve and execute all dependencies required for the requested step:

| Step | Description |
|------|-------------|
| `extract` | Only extract artifacts from source files. |
| `tree` | Build and validate the artifact tree. |
| `impact` | Perform impact analysis (requires git history). |
| `metrics` | (Default) Calculate project metrics and coverage. |
| `ai` | Perform AI-assisted analysis. |

Example:
```bash
# Run impact analysis only
syntagmax analyze .syntagmax/config.toml impact
```

## Report Output

All analysis outputs (errors, metrics, impact, AI analysis, and optionally the artifact tree) are combined into a single Markdown report file.

- **Default location:** `.syntagmax/reports/report.md`
- **Override with:** `--output <path>` or `--output console` to print to stdout
- **Tree inclusion:** Pass `--render-tree` to include the artifact tree in the report
- **Section order:** Errors → Artifact Tree → Metrics → Impact Analysis → AI Analysis

Example:
```bash
# Generate report with tree to default location
syntagmax --render-tree analyze

# Print report to stdout
syntagmax --output console --render-tree analyze
```

## Metamodel DSL

Syntagmax allows defining a custom metamodel for artifacts and their attributes using a simple DSL. This metamodel is used for static validation of requirements and other artifacts.

**Companion VS Code Extension:** [syntagmax-vscode](https://github.com/flyvercity/syntagmax-vscode)

### Example

```model
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute parent is optional reference to parent
    attribute status is mandatory enum [draft, active, retired]
    attribute verify is optional string
    attribute priority is mandatory integer
```

The attributes `id` and `contents` are always mandatory for all artifacts, but the type is flexible.

### Syntax Reference

Python-style comments (`# ...`) are supported.

| Rule | Description |
|------|-------------|
| `artifact <NAME>:` | Defines a new artifact type. Rules must be indented. |
| `id is <type> [as <schema>]` | Defines the id attribute and its optional schema. |
| `attribute <ATTR> is <presence> [multiple] <type>` | Defines a general attribute rule. |

**Presence:** `mandatory` or `optional`.

**Modifier:**
- `multiple`: (Optional) Allows an attribute to have multiple values. Multiple values are extracted into a list. If a `multiple` attribute is missing, it defaults to an empty list `[]`.

**Types:**
- `string`: Any text.
- `integer`: A whole number.
- `boolean`: `true` or `false`.
  - **Custom Values**: You can define custom truthy and falsy values: `boolean [true: "yes", "on", false: "no", "off"]`. If custom values are defined, validation becomes exhaustive (standard `true`/`false` will be rejected unless explicitly included). Comparison is case-insensitive.
- `reference [to parent]`: A reference to another artifact (e.g., `SRS-001`). The optional `to parent` modifier marks the attribute as a parent indicator, used for building the artifact hierarchy. 
  - **Nominal Revision**: For "via commit" traces, you can specify a parent's revision using the `@` symbol: `parent: SRS-001@c2d94e4`. This allows for impact analysis to identify if a requirement is outdated relative to its parent.
- `enum [<values>]`: A fixed set of allowed values (comma-separated). Add the optional `multiple` modifier to allow the attribute to have multiple values.

### Multiple Enum Extraction

Multiple values for an enum can be specified by repeating the attribute or by using a comma-separated list in a single attribute:

```
[<
ID = REQ-1
allocation = HW
allocation = SW
>>>
This requirement has multiple allocations.
>]
```

Or:

```
[<
ID = REQ-2
allocation = HW, SW
>>>
This requirement also has multiple allocations.
>]
```

### Impact Analysis Logic

When impact analysis is enabled (`[impact] enabled = true`), Syntagmax performs the following checks:

1. **Via Commit**: If a parent reference includes a revision (e.g., `SRS-001@c2d94e4`), Syntagmax compares it with the parent's actual latest revision. If they differ, the link is marked as suspicious.
2. **Via Timestamp**: If no revision is specified and the metamodel trace mode is `timestamp`, the link is marked as suspicious if the parent was modified later than the artifact.

Suspicious links are highlighted in the artifact tree (printed in yellow) and included in the impact analysis report.

> **Note**: Impact analysis requires a clean git worktree. You can bypass this check using the `--allow-dirty-worktree` flag.

### Trace Modes

Metamodel traces can specify an analysis mode:

```model
trace from REQ to SYS is mandatory via commit
trace from SYS to ARCH is optional via timestamp
```

- `via commit`: Requires specific revision pinning in the artifact (e.g. `parent: SYS-001@c2d94e4`).
- `via timestamp`: Uses modification times to detect potential staleness. Defaults to `older` nominal revision if not specified.

### Examples of multiple attributes

Multiple values can be specified by repeating the attribute:

```
[<
ID = REQ-1
tag = security
tag = performance
>>>
This requirement has multiple tags.
>]
```

In this case, `artifact.fields['tag']` will be `['security', 'performance']`.

In Obsidian (YAML):
```yaml
attrs:
  author:
    - Alice
    - Bob
```
This will result in `artifact.fields['author']` being `['Alice', 'Bob']`.

## Editing and Renumbering

Syntagmax provides a command to renumber artifact IDs according to a schema. This is useful when you want to ensure a consistent naming convention across your project.

### Quick Editing Demo

```bash
mkdir tmp
cp -rf ./example/renumber-demo ./tmp/
uv run syntagmax --cwd ./tmp/renumber-demo edit renumber --all
```

### Renumbering Command

To renumber artifacts, use the `edit renumber` command:

```bash
syntagmax edit renumber --all
```

#### Options:
- `--all`: Renumber all artifacts.
- `--atype <type>`: Renumber only artifacts of a specific type.
- `--schema <schema>`: Use a custom schema for renumbering.
- `--dry-run`: Show what changes would be made without actually modifying any files.

### ID Schema Format

The ID schema can include the following macros:
- `{atype}`: The type of the artifact (e.g., `REQ`, `SYS`).
- `{num}`: A sequential number.
- `{num:padding}`: A sequential number with zero-padding (e.g., `{num:3}` for `001`).

Example schema: `myproject-{atype}-{num:4}`

### Bulk Attribute Manipulation

The `edit attrs` command adds, removes, or replaces attributes across all artifacts in an input section. Only the Obsidian driver is supported.

```bash
syntagmax edit attrs [OPTIONS]
```

#### Options:

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --operation` | `add` | Operation: `add`, `del`, or `replace` |
| `-t, --type` | `attr` | Target: `attr` (YAML) or `field` (inline `[FIELD]`) |
| `-n, --name` | — | Attribute name. Omit for `add` to add all mandatory metamodel attributes. |
| `-l, --value` | `TBD` | Attribute value. Defaults to `TBD` for `add`. |
| `-s, --section` | — | Input record name (required) |
| `--csv` | — | CSV file for per-artifact value lookup |
| `--csv-id-column` | `id` | CSV column for artifact ID matching |
| `--csv-value-column` | `value` | CSV column for attribute value |
| `-d, --csv-delimiter` | `,` | CSV column delimiter |
| `--dry-run` | — | Preview changes without modifying files |

#### Examples (Development Environment):

```bash
# Add all missing mandatory attributes (from metamodel) with TBD
uv run syntagmax --cwd ./example/obsidian-driver edit attrs -s software-requirements --dry-run

# Add 'owner' attribute with TBD to all SYS requirements
uv run syntagmax --cwd ./example/obsidian-driver edit attrs -s system-requirements -n owner
```

#### Examples as a Tool

```bash
# Replace 'status' to 'active' across all REQ artifacts
syntagmax edit attrs -s requirements -o replace -n status -l active

# Remove 'verified' from all artifacts in a section
syntagmax edit attrs -s system-requirements -o del -n verified

# Import values from a CSV file (with --value as fallback for unmatched IDs)
syntagmax edit attrs -s requirements -o replace -n doors_id --csv mapping.csv --csv-id-column ext_id --csv-value-column doors_id -l UNKNOWN
```

#### Behavior Notes:

- **add**: Skips artifacts that already have the attribute. Uses `TBD` if no value given.
- **del**: Removes the attribute wherever it exists; no-op otherwise.
- **replace**: Updates existing values in-place (preserving field position); appends if missing.
- **Metamodel-driven add**: Omit `--name` to add all mandatory attributes defined in the metamodel.
- **CSV mapping**: `--csv` takes precedence; `--value` serves as fallback for unmatched IDs.
- **Atomic writes**: All changes are computed in memory before any file is written.

## Publishing

Syntagmax can combine project inputs into structured markdown documents, with optional DOCX/PDF export via Pandoc. Rendering is controlled by `publish.yaml` configuration.

```bash
# Publish all records to separate files
syntagmax publish --all

# Single consolidated document with DOCX export
syntagmax publish --all --single --docx --output ./reports/full-document.md
```

For the full command reference, `publish.yaml` schema, rendering configuration, and DOCX template options, see [docs/reference/publishing.md](docs/reference/publishing.md).

## Tracing Export

Syntagmax can export artifact traceability relationships as CSV or TSV matrices. The export uses left outer join semantics — every lead artifact appears even if it has no links to the target type.

```bash
syntagmax trace [OPTIONS]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--child <type>` | Yes | — | Artifact type of the child (e.g., `REQ`) |
| `--parent <type>` | Yes | — | Artifact type of the parent (e.g., `SYS`) |
| `--forward` / `--reverse` | No | `--forward` | Direction: forward (child→parent) or reverse (parent→child) |
| `--attribute <name>` | No | — | Additional lead artifact attributes to include (repeatable) |
| `--flat` | No | — | Combine multiple linked IDs into semicolon-separated values |
| `--delimiter <char>` | No | `,` | Column delimiter (auto-detects `\t` for `.tsv` output) |
| `--plugin <name>` | No | — | Delegate export to a named plugin |
| `--output <path>` | No | `.syntagmax/reports/trace.csv` | Output path (use `console` for stdout) |
| `-f, --config-file` | No | `.syntagmax/config.toml` | Path to config file |

### Forward vs Reverse

- **Forward** (default): Lead artifacts are children. Each row shows a child ID and its linked parent ID(s).
- **Reverse**: Lead artifacts are parents. Each row shows a parent ID and its linked child ID(s).

### Left Outer Join

All lead artifacts appear in the output even if they have no links to the target type. Unlinked artifacts have an empty linked ID column, making it easy to spot coverage gaps.

### Flat Mode

Without `--flat`, a child with multiple parents produces one row per link. With `--flat`, all linked IDs are combined into a single semicolon-separated cell.

### Examples

```bash
# Forward matrix (REQ → SYS) as CSV
syntagmax trace --child REQ --parent SYS

# Reverse matrix with attributes
syntagmax trace --child REQ --parent SYS --reverse --attribute title

# Flat mode, TSV output
syntagmax trace --child REQ --parent SYS --flat --output .syntagmax/reports/trace.tsv

# Export to stdout
syntagmax trace --child REQ --parent SYS --output console

# Use a plugin for export
syntagmax trace --child REQ --parent SYS --plugin tsv-export
```

## Plugins

Syntagmax supports a plugin system that allows custom transformations during the publish pipeline. Plugins are distributed separately from the core project — either as local Python files or as installable packages.

### Configuration

Plugins are declared in `config.toml` via `[[plugin]]` blocks. They execute in the order listed.

```toml
[[plugin]]
name = "add-header"
source = "local"
enabled = true

[plugin.params]
title = "My Document"
version = "2.0"

[[plugin]]
name = "syntagmax-company-plugin"
source = "package"

[plugin.params]
company = "Acme Corp"
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | — | Plugin name (used for discovery) |
| `source` | Yes | — | `"local"` or `"package"` |
| `enabled` | No | `true` | Set to `false` to disable without removing |
| `params` | No | `{}` | Plugin-specific parameters |

### Plugin Hooks

A plugin is a Python module exposing one or more of:

```python
from syntagmax.blocks import BlockTree
from syntagmax.config import Config

def transform_blocks(tree: BlockTree, config: Config, params: dict) -> BlockTree:
    """Called after block tree is built, before rendering."""
    ...

def transform_markdown(markdown: str, config: Config, params: dict) -> str:
    """Called after markdown is rendered, before writing to file."""
    ...
```

For tracing export, a plugin can implement:

```python
from syntagmax.trace import TraceMatrix
from syntagmax.config import Config

def export_trace(matrix: TraceMatrix, config: Config, params: dict) -> None:
    """Called instead of the built-in CSV writer when --plugin is specified.
    The plugin is responsible for writing output (file, stdout, etc.)."""
    ...
```

Hooks are called in config order. Each hook must return the correct type (`BlockTree` or `str`); returning `None` or a wrong type halts the pipeline with an error. The `export_trace` hook returns `None` (the plugin handles output directly).

### Local Plugins

Place Python files in `.syntagmax/plugins/` relative to the config file:

```
.syntagmax/
├── config.toml
└── plugins/
    ├── my-transform.py           # Single-file plugin
    └── complex-transform/        # Directory plugin
        ├── __init__.py
        └── helpers.py
```

### Package Plugins

Install a Python package that registers an entry-point:

```toml
# In the plugin package's pyproject.toml:
[project.entry-points."syntagmax.plugins"]
my-plugin-name = "my_plugin_module"
```

Then reference it in your config with `source = "package"`.

### Error Handling

- If a plugin cannot be found or loaded, the pipeline halts immediately.
- If a hook raises an exception, the full traceback is logged at DEBUG level, and the pipeline halts with a clear error message naming the plugin.

### Example

See `example/plugin-demo/` for a working example with two local plugins demonstrating both hook types.

```bash
uv run syntagmax --cwd ./example/plugin-demo publish .syntagmax/reports/output.md
```

See `example/trace-tsv-plugin/` for a working example of the `export_trace` hook that exports as TSV.

```bash
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --plugin tsv-export
```

## Required Improvements

- Implement automatic change propagation
- Enhance AI-based analysis and tracing

## MCP Server

Syntagmax includes a Model Context Protocol (MCP) server that allows LLMs to interact with your requirements directly.

### Tools

- `list_artifacts`: Returns a list of all artifacts in the system.
- `search_artifacts`: Search for requirements by keyword.
- `get_artifact_content`: Fetch full details of a specific requirement (including traceability).

### Running the Server

To start the server using Server-Sent Events (SSE):

```bash
syntagmax mcp run .syntagmax/config.toml --transport sse --port 8000
```

### Sample Configuration

To use Syntagmax with an MCP client that supports SSE, point it to the server's endpoint:

```json
{
  "mcpServers": {
    "syntagmax": {
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

Note: When running via SSE, the server must be started manually or managed by a process manager before the client connects.
