# Plugins Reference

Syntagmax supports a plugin system that allows custom transformations during the publish pipeline and custom tracing export formats. Plugins are distributed separately from the core project — either as local Python files or as installable packages.

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
| `params` | No | `{}` | Plugin-specific parameters passed to every hook |

## Plugin Discovery

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

The plugin name must match the filename (without `.py`) or directory name.

### Package Plugins

Install a Python package that registers an entry-point:

```toml
# In the plugin package's pyproject.toml:
[project.entry-points."syntagmax.plugins"]
my-plugin-name = "my_plugin_module"
```

Then reference it in your config with `source = "package"`.

## Hooks

A plugin module may implement one or more of the following hooks. All hooks receive `params: dict` — the plugin-specific parameters from `[plugin.params]` in config.

### `transform_blocks`

```python
from syntagmax.blocks import BlockTree
from syntagmax.config import Config

def transform_blocks(tree: BlockTree, config: Config, params: dict) -> BlockTree:
    """Called after the block tree is built, before rendering.

    Must return a BlockTree instance.
    """
    ...
```

Called during the `publish` pipeline. Receives the full block tree and must return a (possibly modified) `BlockTree`. Returning `None` or a wrong type halts the pipeline with an error.

### `transform_markdown`

```python
def transform_markdown(markdown: str, config: Config, params: dict) -> str:
    """Called after markdown is rendered, before writing to file.

    Must return a string.
    """
    ...
```

Called during the `publish` pipeline after rendering. Receives the rendered markdown string and must return a string.

### `filter_block`

```python
from syntagmax.blocks import Block, FileRecord
from syntagmax.config import Config

def filter_block(block: Block, file_record: FileRecord, config: Config, params: dict) -> Block | None:
    """Called per-block after tree transforms, before rendering.

    Return a Block instance to keep/modify, or None to omit the block.
    """
    ...
```

Activated via `--pre-filter <plugin-name>` on the `publish` command. Runs **after** `transform_blocks` but **before** rendering. Returning `None` omits the block; returning a value that is neither a `Block` instance nor `None` halts the pipeline.

> **Note:** The pre-publishing filter applies only to the `publish` command.

### `export_trace`

```python
from syntagmax.trace import TraceMatrix
from syntagmax.config import Config

def export_trace(matrix: TraceMatrix, config: Config, params: dict) -> None:
    """Called instead of the built-in CSV writer when trace plugins are configured.

    The plugin is responsible for writing output (file, stdout, network, etc.).
    Returns None.
    """
    ...
```

Activated when the `[trace]` config section lists the plugin name. See [configuration.md](configuration.md#trace-export-trace) for the config schema.

When `trace.plugins` is non-empty, all listed plugins run sequentially — each receives the same trace matrix. When the list is empty (or the `[trace]` section is absent), the built-in CSV/TSV writer is used.

## TraceMatrix Reference

The `TraceMatrix` dataclass provides all data needed for custom trace export:

```python
@dataclass
class TraceMatrix:
    direction: str          # "forward" or "reverse"
    child_type: str         # Artifact type of the child (--child CLI arg)
    parent_type: str        # Artifact type of the parent (--parent CLI arg)
    attribute_names: list[str]        # Additional attribute columns (--attribute)
    records: list[TraceRecord]        # Matrix rows
    record_names: dict[str, str]      # Artifact ID → input record name
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `direction` | `str` | `"forward"` (child→parent) or `"reverse"` (parent→child) |
| `child_type` | `str` | Artifact type of the child, as passed via `--child` |
| `parent_type` | `str` | Artifact type of the parent, as passed via `--parent` |
| `attribute_names` | `list[str]` | Names of additional attributes requested via `--attribute` |
| `records` | `list[TraceRecord]` | All matrix rows (see below) |
| `record_names` | `dict[str, str]` | Maps artifact ID → input record name (e.g. `"software-requirements"`) |

### `record_names`

Contains entries for every artifact ID that appears in the matrix — both lead and linked sides. This tells you which input section each artifact belongs to.

- Unresolved references (artifact IDs not present in the project) are **excluded** from the dict.
- Artifacts whose input record is not set map to an empty string `""`.

```python
# Example: look up input record for an artifact
section = matrix.record_names.get('REQ-001', '')  # e.g. "software-requirements"
```

### TraceRecord

```python
@dataclass
class TraceRecord:
    record_number: int      # 1-based sequential row index
    lead_id: str            # Lead artifact ID (child in forward, parent in reverse)
    linked_id: str          # Linked artifact ID (or "" if none; "; "-separated in flat mode)
    attributes: dict[str, str]  # Attribute values for the lead artifact
```

### Example Plugin

```python
from syntagmax.trace import TraceMatrix

def export_trace(matrix: TraceMatrix, config, params: dict) -> None:
    for record in matrix.records:
        lead_section = matrix.record_names.get(record.lead_id, '')
        linked_section = matrix.record_names.get(record.linked_id, '')
        print(f'{record.lead_id} [{lead_section}] -> {record.linked_id} [{linked_section}]')
    print(f'Child type: {matrix.child_type}, Parent type: {matrix.parent_type}')
```

## Localization

All hooks receive the `config` object, which includes the resolved output language as `config.language` (`'en'` or `'ru'`). Plugins that produce user-facing text (e.g., custom headers, labels, or report sections) can use this to localize their output.

To use the Syntagmax translation infrastructure directly:

```python
from syntagmax.i18n import _

def transform_markdown(markdown: str, config, params: dict) -> str:
    # _() returns the translated string for the active language
    header = _("Custom Section")
    return f"## {header}\n\n{markdown}"
```

Alternatively, plugins can branch on `config.language` for simple cases:

```python
def transform_markdown(markdown: str, config, params: dict) -> str:
    title = "Пользовательский раздел" if config.language == 'ru' else "Custom Section"
    return f"## {title}\n\n{markdown}"
```

> **Note:** The `publish` command renders user content as-is and is not subject to localization. Plugin hooks in the publish pipeline should only localize their own injected labels, not user artifact content.

## Hook Execution Order

For `publish`:
1. `transform_blocks` (all plugins, in config order)
2. `filter_block` (single plugin specified by `--pre-filter`)
3. Rendering
4. `transform_markdown` (all plugins, in config order)

For `trace`:
1. `export_trace` (all plugins listed in `[trace] plugins`, in order)

## Error Handling

- If a plugin cannot be found or loaded, the pipeline halts immediately with a `FatalError`.
- If a hook raises an exception, the full traceback is logged at DEBUG level, and the pipeline halts with a clear error message naming the plugin.
- Returning an invalid type from a hook (e.g. `None` from `transform_blocks`) halts the pipeline.

## Examples

### Publish plugins

See `example/plugin-demo/` for a working example with local plugins demonstrating `transform_blocks`, `transform_markdown`, and `filter_block` hooks:

```bash
uv run syntagmax --cwd ./example/plugin-demo publish --all .syntagmax/outputs/output.md
```

Filter demo (omits draft artifacts):

```bash
uv run syntagmax --cwd ./example/plugin-demo publish --pre-filter redact-draft --all --single --output .syntagmax/outputs/filtered.md
```

### Trace export plugin

See `example/trace-tsv-plugin/` for a working `export_trace` hook that exports as TSV:

```bash
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS
```
