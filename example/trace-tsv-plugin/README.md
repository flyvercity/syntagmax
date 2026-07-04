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

## Running

Export forward traceability matrix (REQ → SYS) via the TSV plugin:

```bash
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --plugin tsv-export
```

Export with attributes:

```bash
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --attribute title --attribute status --plugin tsv-export
```

Export reverse matrix (SYS → REQ):

```bash
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --reverse --plugin tsv-export
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

You can also export CSV/TSV directly without a plugin using the built-in writer:

```bash
# CSV (default)
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS

# TSV via file extension auto-detection
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --output .syntagmax/reports/trace.tsv

# TSV via explicit delimiter
uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --delimiter "\t"
```
