# Plugins Reference

Syntagmax supports a plugin system that allows custom transformations during the publish pipeline. Plugins are distributed separately from the core project — either as local Python files or as installable packages.

## Configuration

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

## Plugin Hooks

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

## Pre-Publishing Block Filter

A plugin can also implement a per-block filter hook, activated via `--pre-filter <plugin-name>` on the `publish` command:

```python
from syntagmax.blocks import Block, FileRecord
from syntagmax.config import Config

def filter_block(block: Block, file_record: FileRecord, config: Config, params: dict) -> Block | None:
    """Called per-block after tree transforms, before rendering.
    Return a Block instance to keep/modify, or None to omit the block."""
    ...
```

This hook runs **after** `transform_blocks` but **before** rendering. It receives each block individually along with its parent `FileRecord` (providing file path context). Returning `None` omits the block from the published output; returning a value that is neither a `Block` instance nor `None` halts the pipeline with a fatal error.

The `--pre-filter` option requires the plugin to be configured in `config.toml`. A single plugin module can implement `filter_block` alongside other hooks (`transform_blocks`, `transform_markdown`).

> **Note:** The pre-publishing filter applies only to the `publish` command. Other interfaces (e.g., the MCP server) do not apply publish-time filters.

## Local Plugins

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

## Package Plugins

Install a Python package that registers an entry-point:

```toml
# In the plugin package's pyproject.toml:
[project.entry-points."syntagmax.plugins"]
my-plugin-name = "my_plugin_module"
```

Then reference it in your config with `source = "package"`.

## Error Handling

- If a plugin cannot be found or loaded, the pipeline halts immediately.
- If a hook raises an exception, the full traceback is logged at DEBUG level, and the pipeline halts with a clear error message naming the plugin.

## Examples

See `example/plugin-demo/` for a working example with local plugins demonstrating `transform_blocks`, `transform_markdown`, and `filter_block` hooks.

```bash
uv run syntagmax --cwd ./example/plugin-demo publish --all .syntagmax/reports/output.md
```

To demonstrate the `filter_block` hook (omits draft artifacts):

```bash
uv run syntagmax --cwd ./example/plugin-demo publish --pre-filter redact-draft --all --single --output .syntagmax/reports/filtered.md
```

See `example/trace-tsv-plugin/` for a working example of the `export_trace` hook that exports as TSV.

```bash
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --plugin tsv-export
```
