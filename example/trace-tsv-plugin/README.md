# Trace TSV Plugin Example

This example demonstrates the `export_trace` plugin hook by exporting a traceability matrix as a tab-separated values (TSV) file instead of the default CSV.

## Structure

```
example/trace-tsv-plugin/
├── .syntagmax/
│   ├── config.toml           # Project config with tsv-export plugin
│   ├── project.syntagmax     # Metamodel with SYS and REQ types
│   └── plugins/
│       └── tsv-export.py     # Plugin implementing export_trace
├── SYS/                      # System requirements
│   ├── SYS-001.md
│   └── SYS-002.md
├── REQ/                      # Software requirements (children of SYS)
│   ├── REQ-001.md            # Links to SYS-001
│   ├── REQ-002.md            # Links to SYS-002
│   └── REQ-003.md            # Derived (no parent) - demonstrates left outer join
└── README.md
```

## Configuration

The `[trace]` section in `config.toml` declares which plugins handle trace export:

```toml
[[plugin]]
name = "tsv-export"
source = "local"

[plugin.params]
output = ".syntagmax/outputs/trace.tsv"

[trace]
plugins = ["tsv-export"]
```

When `trace.plugins` is non-empty, all listed plugins run sequentially — each receives the same trace matrix. When the list is empty (or the `[trace]` section is absent), the built-in CSV/TSV writer is used.

## Running

Export forward traceability matrix (REQ → SYS) via the configured TSV plugin:

```bash
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS
```

Export with attributes:

```bash
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --attribute title --attribute status
```

Export reverse matrix (SYS → REQ):

```bash
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --reverse
```

## Plugin API

The `export_trace` hook receives:

```python
from syntagmax.trace import TraceMatrix
from syntagmax.config import Config

def export_trace(matrix: TraceMatrix, config: Config, params: dict) -> None:
    """
    matrix: The built TraceMatrix with all records
    config: Syntagmax project configuration
    params: Plugin-specific parameters from config.toml [plugin.params]
    """
    ...
```

### TraceMatrix Fields

| Field | Type | Description |
|-------|------|-------------|
| `direction` | `str` | `"forward"` or `"reverse"` |
| `child_type` | `str` | Artifact type of the child (as invoked via `--child`) |
| `parent_type` | `str` | Artifact type of the parent (as invoked via `--parent`) |
| `attribute_names` | `list[str]` | Additional attribute columns requested via `--attribute` |
| `records` | `list[TraceRecord]` | Matrix rows (see below) |
| `record_names` | `dict[str, str]` | Maps artifact ID → input record name (e.g. `"software-requirements"`) |

The `record_names` dict contains entries for every artifact ID that appears in the matrix (both lead and linked sides). Unresolved references (artifact IDs not present in the project) are excluded. Artifacts whose input record is not set map to an empty string.

#### Example: using record_names

```python
for record in matrix.records:
    lead_section = matrix.record_names.get(record.lead_id, '')
    linked_section = matrix.record_names.get(record.linked_id, '')
    print(f'{record.lead_id} ({lead_section}) -> {record.linked_id} ({linked_section})')
```

The plugin is responsible for writing the output (file, stdout, network, etc.). See `.syntagmax/plugins/tsv-export.py` for the full implementation.

### Plugin Params: include_record_names

Set `include_record_names = true` in `[plugin.params]` to add `LeadRecord` and `LinkedRecord` columns to the TSV output:

```toml
[plugin.params]
output = ".syntagmax/outputs/trace.tsv"
include_record_names = true
```

## Without Plugin (built-in CSV)

To use the built-in CSV/TSV writer instead, remove the `[trace]` section (or set `plugins = []`):

```bash
# CSV (default)
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS

# TSV via file extension auto-detection
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --output .syntagmax/outputs/trace.tsv

# TSV via explicit delimiter
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --delimiter "\t"
```
