# Embedding API Reference (`syntagmax.api`)

Syntagmax is a CLI-first tool, but it can also be embedded directly as a Python library. The `syntagmax.api` module is a small, sanctioned, additive facade that lets a host application (for example, a web GUI running the core in-process) open a project, read its artifacts, run analysis, and perform writes — while delegating all domain logic back to the core. The CLI continues to work unchanged.

This page documents the actual implemented surface in `src/syntagmax/api.py`.

---

## Quick Start

```python
from syntagmax import api

# Open a project by pointing at its config.toml.
session = api.open_project('example/obsidian-driver/.syntagmax/config.toml')

# Read: structured views, not formatted strings.
for view in session.query(atype='REQ'):
    print(view.aid, view.fields.get('title'))

req = session.get('REQ-001')
if req is not None:
    print(req.aid, req.atype, req.parents)

# Search: case-insensitive, AND semantics across aid, atype, and all fields
# (including the body contents).
hits = session.search('non-blocking serializes')

# Analyse: structured diagnostics plus pass-through metrics and impact.
result = session.analyse()
for diag in result.diagnostics:
    print(diag.severity, diag.category, diag.location, diag.message)

# Write (obsidian driver only in this phase): edit returns the updated view.
updated = session.edit('REQ-001', fields={'status': 'retired'})
print(updated.fields.get('status'))
```

The facade adds no HTTP or async concepts and remains fully synchronous. `FatalError` and `RMSException` propagate unchanged out of `open_project` and every `Session` method; the facade never swallows them, preserving the fatal-config contract.

---

## `open_project`

```python
def open_project(config_path: str | Path, *, options: Options | None = None) -> Session
```

Opens a Syntagmax project and returns a `Session`. The path is resolved, and the facade builds a `syntagmax.config.Config` internally from `Options` — the host never constructs the CLI-shaped `Params` dict. When `options` is omitted, defaults matching the current CLI defaults are used.

A broken or missing config path raises `FatalError`.

---

## `Options`

A dataclass carrying library-facing options with defaults matching the current CLI defaults. The host constructs an `Options` and the facade owns the translation to the internal `Params`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `render_tree` | `bool` | `False` | Render the traceability tree during processing. |
| `no_git` | `bool` | `False` | Skip Git-backed revision population. When set, `latest_revision` is `None` and impact analysis is skipped. |
| `allow_dirty_worktree` | `bool` | `False` | Permit analysis against a dirty worktree. |
| `suppress_tracing` | `bool` | `False` | Suppress tracing during processing. |
| `tasks` | `bool` | `False` | Force impact task generation (mirrors the CLI `--tasks` flag). |
| `language` | `str` | `'en'` | Processing language. |
| `warnings_as_errors` | `bool` | `False` | Treat warnings as errors. |
| `log_level` | `str \| None` | `None` | Optional log level; omitted from `Params` when `None`. |

---

## `Session`

A synchronous, thread-safe read-and-write handle over a populated project.

### Thread-safety

The `Session` holds an internal `threading.Lock` guarding a cached `ArtifactMap`. Lazy computation and `reload()` acquire the same lock, so a multi-threaded host (for example, a FastAPI worker pool sharing a single `Session`) cannot race on cache invalidation.

### Read methods

| Method | Returns | Description |
|--------|---------|-------------|
| `artifacts()` | `ArtifactMap` | The populated artifact graph. Wraps the canonical sequence `extract → build_artifact_map → populate_pids → build_tree → analyse_tree` exactly once and caches the result. |
| `get(aid)` | `ArtifactView \| None` | The view for `aid`, or `None` when absent. |
| `query(*, atype=None)` | `list[ArtifactView]` | All views, optionally filtered by `atype`. The synthetic `ROOT` pseudo-artifact is always excluded. |
| `search(q)` | `list[ArtifactView]` | Case-insensitive search with AND semantics. Matches against `aid`, `atype`, and all `fields` including the `contents` body text; a multi-term query matches only when every whitespace-separated term is found across those searchable strings. |

### Analysis

```python
def analyse(self) -> AnalysisResult
```

Runs the analysis path (delegating to `main.process('metrics', config)`, whose DAG includes `impact` and `metrics`), converts every `Report.errors` entry to a public `Diagnostic`, and passes `metrics` and `impact` through unchanged. With `no_git=True`, `populate_revisions` and `impact` are skipped, so `impact` is `None`.

### Write methods

The write seam is driver-agnostic, but only the **obsidian** driver implements it in this phase (see [Capability model](#capability-model)). Writes mutate files on disk; the core never commits them — Git remains the host's responsibility.

```python
def edit(self, aid: str, *, fields: dict[str, str | None] | None = None, body: str | None = None) -> ArtifactView
def create(self, *, driver_or_record: str | InputRecord, target_file: str, atype: str, aid: str, fields: dict | None = None, body: str = '') -> ArtifactView
def delete(self, aid: str) -> None
```

- `edit` sets one or more fields and/or the body of an existing artifact, reloads the cache, and returns the updated `ArtifactView` so the host can refresh its UI without a second `get()` call. A field value of `None` deletes that YAML attribute key; a non-`None` value sets or replaces it; a non-`None` `body` replaces the `contents` body text.
- `create` adds a new artifact to `target_file` (creating any missing parent directories) and returns the created `ArtifactView`. `aid` is required in this phase; auto-ID generation is out of scope. `target_file` is validated to resolve within the project root.
- `delete` removes an artifact's marked fragment. When the removed artifact was the only artifact in its file, the underlying file is deleted.

`edit`, `create`, and `delete` on a driver without an implementation raise `UnsupportedOperation` (a subclass of `RMSException`).

### Capability model

```python
def capabilities(self, driver_or_record: str | InputRecord) -> set[str]
```

Returns the write capabilities for a driver or record, read from the extractor's `WRITE_CAPABILITIES` set. A host can call this to present only valid actions. In this phase:

| Driver | Capabilities |
|--------|--------------|
| `obsidian` | `{'edit', 'create', 'delete'}` |
| Any other driver (for example, `text`) | `set()` (empty) |

A string argument is treated as a driver name (the first matching configured input record is used, or a synthetic record is fabricated); an `InputRecord` is used directly.

### `reload()`

```python
def reload(self) -> None
```

Forces recomputation by clearing the cache under the lock. The write methods call it automatically after each mutation.

**Full-reparse trade-off and the create/delete-file caveat:** `reload()` re-runs the full pipeline, so for very large repositories a single-artifact write incurs a full re-parse. This is an accepted Phase-1 limitation; incremental reload is future work. In-place `edit` changes are reflected after `reload()`, but newly created or deleted **files** are not picked up until the project is re-opened with a fresh `open_project` call — the input-record file lists are resolved at open time. A host that creates or deletes files should re-open the project to see them.

---

## `ArtifactView`

A structured, public read view over an internal `Artifact`. It is deliberately distinct from the internal `Artifact` so the facade has a stable public contract. Serialisation (for example, to JSON) is the host's responsibility.

| Field | Type | Description |
|-------|------|-------------|
| `aid` | `str` | Artifact ID. |
| `atype` | `str` | Artifact type. |
| `fields` | `dict[str, str \| list[str]]` | Attribute fields, including the `contents` body text. |
| `parents` | `list[dict[str, object]]` | One entry per parent link, each with keys `pid`, `nominal_revision`, and `is_suspicious`. |
| `children` | `list[str]` | Sorted list of child artifact IDs. |
| `latest_revision` | `Revision \| None` | Latest Git revision, or `None` (for example, when `no_git` is set). |

---

## `Diagnostic`

The public, structured representation of a single analysis issue — the host-facing projection of the core's `ReportError`. Hosts never parse flat diagnostic strings.

| Field | Type | Description |
|-------|------|-------------|
| `severity` | `str` | `error` or `warning`. |
| `artifact_id` | `str \| None` | The offending artifact ID, when known. |
| `rule` | `str \| None` | The rule name, falling back to `category` when the source error has no explicit rule. |
| `category` | `str` | Diagnostic category (for example, `extraction`, `structure`, `schema`, `attribute`, `reference`, `trace`, `duplicate`). |
| `location` | `str` | File and line location, or an empty string when neither is present. |
| `message` | `str` | Human-readable message. |

### `ReportError → Diagnostic` mapping

The facade owns a fixed, exact mapping from the core `ReportError` to the public `Diagnostic`:

- `severity = e.severity`
- `artifact_id = e.artifact_id`
- `rule = e.rule or e.category` (falls back to the category when `rule` is unset)
- `category = e.category`
- `location = f'{e.file_path}:{e.line_range[0]}-{e.line_range[1]}'` when both `file_path` and `line_range` are present; otherwise `e.file_path or ''` (an empty string when there is no file path)
- `message = e.message`

---

## `AnalysisResult`

The structured result of `Session.analyse()`.

| Field | Type | Description |
|-------|------|-------------|
| `diagnostics` | `list[Diagnostic]` | All analysis issues, mapped from `Report.errors`. |
| `metrics` | `Any` | Passed through unchanged from the core `Report` (`benedict` or `None`). |
| `impact` | `Any` | Passed through unchanged from the core `Report` (`benedict` or `None`; `None` when `no_git` is set). |

---

## See also

- [Configuration Reference](configuration.md) — including the `impact.task_dir` setting for redirecting generated impact tasks.
- [Paths Reference](paths.md) — how Syntagmax resolves directories and file references.
