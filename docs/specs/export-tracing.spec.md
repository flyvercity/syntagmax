# Export Artifact Tree as Tracing Tables

## Problem Statement

Users need to export artifact traceability relationships as forward (child→parent) or reverse (parent→child) matrices in CSV format, with optional attribute columns, a flat mode to consolidate multiple links per row, and a plugin hook for custom export formats.

## Requirements

- New `trace` CLI subcommand
- `--child <type>` and `--parent <type>` (required) to specify artifact types
- `--forward` / `--reverse` flag to choose direction (default forward)
- `--attribute <name>` repeatable option for additional lead-object attribute columns
- `--flat` flag to merge multiple linked objects into semicolon-separated values
- `--plugin <name>` to delegate export to a plugin instead of CSV
- Default output file: `.syntagmax/reports/trace.csv`, with `--output console` for stdout
- Plugin hook: `export_trace(matrix, config, params) -> None` — plugin handles output itself
- Update README.md and docs/technical-summary.md
- Example plugin for tab-separated format

## Background

- The project uses Click for CLI, pydantic for config models, and pytest for tests
- Artifact parent-child links are stored in `Artifact.pids` (list of parent IDs) and `Artifact.children` (set of child IDs)
- The existing pipeline resolves parent links via `populate_pids()` and `build_tree()`
- The plugin system already has `load_plugins()`, `LoadedPlugin`, and uses `FatalError` for errors
- The existing plugin hook pattern is: check `hasattr(module, hook_name)`, call it, validate return type
- Output default path pattern matches `.syntagmax/reports/report.md`

## Proposed Solution

```mermaid
flowchart TD
    A[CLI: syntagmax trace] --> B[Load Config & Run Pipeline up to 'tree']
    B --> C[Filter artifacts by child/parent atype]
    C --> D[Build TraceMatrix dataclass]
    D --> E{--plugin specified?}
    E -->|No| F[CSV Writer: format matrix as CSV]
    E -->|Yes| G[Load plugin, call export_trace hook]
    F --> H{--output}
    H -->|file| I[Write to file]
    H -->|console| J[Print to stdout]
    G --> K[Plugin handles output]
```

### Data Model

```python
@dataclass
class TraceRecord:
    record_number: int
    lead_id: str          # ChildID (forward) or ParentID (reverse)
    linked_id: str        # ParentID (forward) or ChildID (reverse) — may be "; " separated in flat mode
    attributes: dict[str, str]  # Additional lead attributes

@dataclass
class TraceMatrix:
    direction: str        # "forward" or "reverse"
    child_type: str
    parent_type: str
    attribute_names: list[str]
    records: list[TraceRecord]
```

### CLI Interface

```bash
uv run syntagmax trace [OPTIONS]
```

Options:
- `--child <type>` — the `atype` of child artifacts (required)
- `--parent <type>` — the `atype` of parent artifacts (required)
- `--forward` / `--reverse` — direction flag (mutually exclusive, default forward)
- `--attribute <name>` — additional attributes of the lead object to include as columns (optional, repeatable)
- `--flat` — combine multiple linked objects into a single record with semicolon-separated list (optional flag)
- `--plugin <name>` — use a named plugin instead of CSV output
- `--output <path>` — output file path (default: `.syntagmax/reports/trace.csv`), use `console` for stdout
- `-f / --config-file` — path to config file (default: `.syntagmax/config.toml`)

### Forward Matrix Logic

1. Iterate all artifacts where `atype == child_type`
2. For each child artifact, find its parents where `atype == parent_type` (from `pids` resolved against `ArtifactMap`)
3. Without `--flat`: emit one row per (child, parent) pair
4. With `--flat`: emit one row per child, joining all parent IDs with `"; "`

### Reverse Matrix Logic

1. Iterate all artifacts where `atype == parent_type`
2. For each parent artifact, find its children where `atype == child_type` (from `children` set)
3. Without `--flat`: emit one row per (parent, child) pair
4. With `--flat`: emit one row per parent, joining all child IDs with `"; "`

### CSV Output Format

Header columns depend on direction:
- Forward: `RecordNumber, ChildID, ParentID, <attr1>, <attr2>, ...`
- Reverse: `RecordNumber, ParentID, ChildID, <attr1>, <attr2>, ...`

Uses Python's `csv` module for proper escaping.

### Plugin Hook

New hook signature added to the plugin system:

```python
from syntagmax.trace import TraceMatrix
from syntagmax.config import Config

def export_trace(matrix: TraceMatrix, config: Config, params: dict) -> None:
    """Called instead of CSV writer when --plugin is specified.
    Plugin is responsible for writing output (file, stdout, etc.)."""
    ...
```

Execution:
- The named plugin is looked up from `config.plugins()` by name
- If the plugin doesn't have an `export_trace` hook, raise `FatalError`
- If the hook raises an exception, log traceback at DEBUG level and raise `FatalError`

### Example Output

#### Forward Matrix

| RecordNumber | ChildID | ParentID | ChildAttrA   | ChildAttrB   |
| ------------ | ------- | -------- | ------------ | ------------ |
| 1            | LLR-001 | HLR-001  | custom-val-a | custom-val-b |
| 2            | LLR-002 | HLR-002  | custom-val-c | custom-val-d |
| 3            | LLR-002 | HLR-003  | custom-val-c | custom-val-d |

#### Forward Matrix (Flat)

| RecordNumber | ChildID | ParentID        | ChildAttrA   | ChildAttrB   |
| ------------ | ------- | --------------- | ------------ | ------------ |
| 1            | LLR-001 | HLR-001         | custom-val-a | custom-val-b |
| 2            | LLR-002 | HLR-002; HLR-003 | custom-val-c | custom-val-d |

#### Reverse Matrix

| RecordNumber | ParentID | ChildID | ParentAttrA  | ParentAttrB  |
| ------------ | -------- | ------- | ------------ | ------------ |
| 1            | HLR-001  | LLR-001 | custom-val-a | custom-val-b |
| 2            | HLR-001  | LLR-002 | custom-val-a | custom-val-b |
| 3            | HLR-002  | LLR-003 | custom-val-c | custom-val-d |

## Task Breakdown

### Task 1: TraceMatrix data model and matrix-building logic

**Objective:** Create the `TraceMatrix` and `TraceRecord` dataclasses, and implement the core function that takes an `ArtifactMap` plus parameters and produces a `TraceMatrix`.

**Implementation guidance:**
- Create `src/syntagmax/trace.py` with `TraceRecord` and `TraceMatrix` dataclasses
- Implement `build_trace_matrix(artifacts: ArtifactMap, child_type: str, parent_type: str, direction: str, attributes: list[str], flat: bool) -> TraceMatrix`
- For forward: iterate artifacts where `atype == child_type`, find parents where `atype == parent_type` (from `pids`). One row per (child, parent) pair unless `--flat`.
- For reverse: iterate artifacts where `atype == parent_type`, find children where `atype == child_type` (from `children`). One row per (parent, child) pair unless `--flat`.
- In flat mode, group by lead and join linked IDs with `"; "`.
- Sequential record numbering starts at 1.

**Test requirements:**
- Test forward matrix with simple 1:1 parent-child links
- Test forward matrix with 1:N (child has multiple parents of target type)
- Test reverse matrix with 1:N (parent has multiple children)
- Test `--flat` mode collapses multiple linked IDs
- Test that artifacts not matching the requested types are excluded
- Test attribute extraction populates the dict correctly
- Test empty result (no matching links)

**Demo:** `uv run pytest tests/test_trace_export.py` passes; a mock artifact map produces the expected `TraceMatrix`.

---

### Task 2: CSV writer for TraceMatrix

**Objective:** Implement a function that serializes a `TraceMatrix` to CSV format (as a string).

**Implementation guidance:**
- In `src/syntagmax/trace.py`, add `render_trace_csv(matrix: TraceMatrix) -> str`
- Use Python's `csv` module with `io.StringIO`
- Header row: `RecordNumber`, lead column name (based on direction), linked column name, then attribute column names
- Column naming: for forward, columns are `RecordNumber, ChildID, ParentID, <attr1>, <attr2>...`. For reverse: `RecordNumber, ParentID, ChildID, <attr1>, <attr2>...`

**Test requirements:**
- Test CSV output matches expected format for a simple forward matrix
- Test CSV output for reverse matrix
- Test that attributes appear as additional columns
- Test flat mode output with semicolons in linked column

**Demo:** `uv run pytest tests/test_trace_export.py` passes; CSV output can be parsed back and matches expectations.

---

### Task 3: Plugin hook for trace export (`export_trace`)

**Objective:** Extend the plugin system with a new `export_trace` hook that receives the matrix and handles output.

**Implementation guidance:**
- In `src/syntagmax/plugin.py`, add `run_trace_export(plugin: LoadedPlugin, matrix: TraceMatrix, config: Config) -> None`
- The function calls `plugin.module.export_trace(matrix, config, plugin.params)` if the hook exists
- If the hook doesn't exist on the named plugin, raise `FatalError`
- If the hook raises, log traceback at DEBUG and raise `FatalError`
- No return type validation needed (returns None)
- The plugin signature: `def export_trace(matrix: TraceMatrix, config: Config, params: dict) -> None`

**Test requirements:**
- Test that a plugin with `export_trace` is called with correct arguments
- Test that a plugin without `export_trace` raises `FatalError`
- Test that exceptions in the hook are wrapped in `FatalError`

**Demo:** `uv run pytest tests/test_trace_export.py` passes; mock plugin receives the matrix.

---

### Task 4: CLI `trace` command wiring

**Objective:** Add the `trace` subcommand to the CLI that orchestrates config loading, pipeline execution, matrix building, and output.

**Implementation guidance:**
- In `cli.py`, add a new `@rms.command` named `trace`
- Options: `--child` (required), `--parent` (required), `--forward`/`--reverse` (mutually exclusive flags, default forward), `--attribute` (multiple), `--flat` (flag), `--plugin` (optional string), `-f/--config-file` (default `.syntagmax/config.toml`), `--output` (default `.syntagmax/reports/trace.csv`)
- Load config, run the pipeline up through `tree` step (reuse `process('tree', config)` or equivalent — need artifacts built with parent links)
- Call `build_trace_matrix(...)` with the resolved artifacts
- If `--plugin`: load that specific plugin from `config.plugins()` by name, call `run_trace_export`
- Else: call `render_trace_csv()`, write to output path or print to stdout if `--output console`

**Test requirements:**
- Integration test: end-to-end with a temp project producing a CSV file
- Test `--output console` prints to stdout
- Test missing `--child`/`--parent` shows error
- Test invalid atype (no matching artifacts) produces empty CSV with header only

**Demo:** `uv run syntagmax --cwd ./example/obsidian-driver trace --child REQ --parent SYS` produces a CSV in `.syntagmax/reports/trace.csv`.

---

### Task 5: Example plugin for tab-separated export

**Objective:** Create an example plugin that exports the trace matrix as TSV instead of CSV, with its own README.

**Implementation guidance:**
- Create `example/trace-tsv-plugin/` directory with:
  - `.syntagmax/config.toml` referencing the plugin and some input records
  - `.syntagmax/plugins/tsv-export.py` implementing `export_trace`
  - `README.md` explaining how the plugin works
- The plugin should write TSV to a file path derived from params (e.g., `params['output']`)
- Include a small set of requirement files for the example

**Test requirements:**
- The example works end-to-end: `uv run syntagmax --cwd ./example/trace-tsv-plugin trace --child REQ --parent SYS --plugin tsv-export`

**Demo:** Running the example produces a `.tsv` file with tab-separated trace data.

---

### Task 6: Documentation updates

**Objective:** Update README.md and docs/technical-summary.md with the new `trace` command and plugin hook.

**Implementation guidance:**
- In `README.md`, add a "Tracing Export" section after "Publishing" covering:
  - Command syntax and all options
  - Forward vs reverse explanation
  - Flat mode
  - Plugin usage
  - Example output
- In `docs/technical-summary.md`, add a bullet under "Traceability & Impact Analysis" mentioning CSV/plugin export
- In the Plugins section of README, document the new `export_trace` hook signature

**Test requirements:**
- No code tests, but verify docs are consistent with implementation

**Demo:** README has clear usage examples for the `trace` command.
