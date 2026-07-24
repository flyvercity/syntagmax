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
output = ".syntagmax/reports/trace.tsv"

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

The plugin is responsible for writing the output (file, stdout, network, etc.). See `.syntagmax/plugins/tsv-export.py` for the full implementation.

## Without Plugin (built-in CSV)

To use the built-in CSV/TSV writer instead, remove the `[trace]` section (or set `plugins = []`):

```bash
# CSV (default)
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS

# TSV via file extension auto-detection
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --output .syntagmax/reports/trace.tsv

# TSV via explicit delimiter
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --delimiter "\t"
```
