# Seed Spec: Library-First Embedding API for Syntagmax

We want to embed `syntagmax` cleanly as a Python library inside a host application (the Syntagmax Web GUI is the first embedder), not just drive it from the CLI. Today the core is CLI-first: reaching a populated artifact graph means open-coding the pipeline, building a `Config` requires a CLI-shaped `Params` dict, the query operations only exist as presentation strings, diagnostics are flat strings, and generated impact tasks cannot be redirected. Every embedder ends up re-implementing core knowledge. This seed adds a small, sanctioned embedding surface so a host can consume Syntagmax as a library and offload domain logic back to the core where it belongs.

This is the recommended outcome of the GUI-side brainstorm (`syntagmax-gui/docs/brainstorms/CORE_OFFLOAD_REPORT.md`, Approach B). Auth, HTTP, sessions, and Git *writes* are deliberately **not** the core's concern — see Non-Goals.

## Guiding Principle

The CLI keeps working exactly as-is. Everything here is additive and lives behind a new `syntagmax.api` module. The library never inspects CLI-shaped state on behalf of an embedder, and it never resolves *who* a user is — identity is always passed in by the host.

## Core Features

### 1. A `syntagmax.api` embedding facade

A single cohesive entry point over one project worktree:

- `open_project(config_path, *, options=Options()) -> Session`
- `Session.artifacts() -> ArtifactMap` — the populated graph, wrapping the existing `extract → build_artifact_map → populate_pids → build_tree → analyse_tree` sequence once, so no embedder open-codes it again.
- `Session.get(aid)`, `Session.query(...)`, `Session.search(q)` — return **structured dataclasses** (id, atype, fields, parents, children, latest revision), not Markdown or formatted text. The host owns serialisation (e.g. to JSON).
- `Session.analyse() -> AnalysisResult` — structured metrics, impact, and diagnostics.
- `Session.edit(...)`, `Session.create(...)`, `Session.delete(...)` — the write seam (see feature 3), with per-driver capability flags.

`Options` is a real dataclass with sensible defaults (`no_git`, `allow_dirty_worktree`, `language`, `render_tree`, `suppress_tracing`, `tasks`, …). The facade builds the `Config` internally from `Options` — the host never fabricates a CLI `Params` dict. `FatalError` / `RMSException` still propagate (fatal-config contract preserved); the host catches them at its own boundary.

### 2. Structured diagnostics (single source of truth)

Introduce a `Diagnostic` dataclass — `{ severity, artifact_id, rule, category, location, message }` — and make analysis, impact, and metrics emit `Diagnostic`s. The existing human-readable strings (`errors: list[str]`, report output) are **derived from** the structured diagnostics, so there is one source of truth and **no duplicated channel**. CLI and report text stay byte-for-byte identical (guarded by golden-output tests). `Session.analyse()` exposes the structured diagnostics so a host can aggregate them by document/folder and bind each entry back to its artifact.

### 3. Driver-agnostic write seam — Obsidian implementation

Generalise the `Extractor` interface with:

- `edit_artifact(...)` — set fields and/or body text on an existing artifact
- `create_artifact(...)` — add a new artifact to a document
- `delete_artifact(...)` — remove an artifact

The base implementations raise `NotImplementedError`. For this phase, **only the `obsidian` driver** implements them (reusing its existing content-producing/update path). Other drivers keep raising a typed `UnsupportedOperation` that the host can surface cleanly. `Session` exposes per-driver capability flags so a host can advertise what is editable. Writes go through the driver to real files on disk — the core does not commit them (see Non-Goals).

### 4. Redirectable impact tasks: `impact.task_dir`

Add a new, separate config setting `impact.task_dir` (distinct from the existing `impact.tasks_dir`). When set, generated impact tasks resolve against it — honouring an **absolute** path as-is (mirroring how `output_path` already works), or relative-to-root otherwise. When unset, behaviour is exactly today's (`tasks/` relative to the config directory, versioned in the worktree). This lets an embedder redirect generated tasks to a separate, non-versioned outputs tree without changing default CLI behaviour.

## Example (embedding)

```python
from syntagmax import api

session = api.open_project("path/to/project/config.toml")

for art in session.query(atype="REQ"):
    print(art.aid, art.fields.get("title"))

result = session.analyse()
for d in result.diagnostics:
    print(d.severity, d.artifact_id, d.rule, d.message)

# Obsidian driver only, this phase:
session.edit("REQ-001", fields={"status": "approved"})
```

## Example (config)

```toml
[impact]
tasks_enabled = true
tasks_dir = "tasks/"                 # unchanged default (relative, versioned)
task_dir  = "/var/lib/host/outputs/demo/tasks"   # NEW: absolute redirect for embedders
```

## Non-Goals (this phase)

- **No Git writes in the core.** Syntagmax works in pair with regular Git and offloads worktree creation, staging, and commits to it; the host (or plain git) owns those. The core stays a read-only Git consumer (blame/log for revisions). Where a commit needs an author identity, the host passes it to git — the core does not discover or commit it.
- **No auth/authorization** in the core — identity is passed in, never resolved by the core.
- **No non-Obsidian write drivers** yet — the seam exists and raises `NotImplementedError` elsewhere.
- **No rebasing the CLI onto the facade.** The CLI is untouched; migrating it onto `syntagmax.api` is a later, separate effort with no impact on embedders.
- **No HTTP/async** — the facade is synchronous; hosts offload it to their own threadpool.

## Tasks

- Add `src/syntagmax/api.py` with `Options`, `open_project`, and `Session` (`artifacts/get/query/search/analyse/edit/create/delete` + capability flags); build `Config` from `Options` with CLI-parity defaults.
- Add a `Diagnostic` dataclass; make analysis/impact/metrics emit diagnostics and derive the existing strings from them; keep `errors: list[str]` and report output identical via golden-output tests.
- Generalise `Extractor` with `edit_artifact/create_artifact/delete_artifact` (base raises `NotImplementedError`); implement for the `obsidian` driver; add a typed `UnsupportedOperation`.
- Add `impact.task_dir` to `ImpactConfig` and a `Config.task_dir()` resolver (absolute as-is, else relative-to-root, unset → current `tasks_dir` behaviour); route task generation through it.
- Tests: facade `Config` parity vs CLI-built; query/get/search over `example/`; structured-diagnostic assertions + golden CLI/report output; Obsidian edit/create/delete round-trip on Windows; `task_dir` default-unchanged and redirect cases.

## Follow-up

- Update `README.md` with a short "Embedding Syntagmax as a library" section.
- Add `docs/reference/` pages: an embedding-API reference and the new `impact.task_dir` config setting.
- Add a `CHANGELOG.md` entry.
- Land all of the above on the `gui-adaptations` branch; upstream/publish manually later.
