# Syntagmax Application Logic — Review Draft

> **Step 1/2 — compact example for human review.**
> This is a behavior map, not yet the exhaustive code audit. Confirm the structure, compression level, and terminology before the full document is produced.

## 0. Evidence and notation

- **Primary runtime:** `src/syntagmax/`; CLI entry: `src/syntagmax/cli.py`.
- **Behavior sources:** implementation + `README.md` + `openwiki/*.md` + tests.
- **Rule form:** `Rxx` = externally visible or load-bearing behavior; `→` = data flow; `FAIL` = fatal/blocked path.
- **Pinned repository facts used:** keep `docs/reference/` in place; new specification docs belong in `docs/specs/`; project uses CalVer `YYYY.M.D`; backend changes require Ruff and pytest. Pin MCP was not available in this session; local `.pin/` files were used instead.

## 1. Product boundary

- Syntagmax = git-friendly requirements-management/RMS tool.
- Core objects: configured **input records** → extracted **artifacts** → artifact map/tree → validation, metrics, trace/impact analysis → Markdown report.
- Separate path: input records → publish **block tree** → Markdown → optional DOCX/PDF.
- Optional surfaces: artifact editing, change/baseline tooling, AI task verification, MCP read access, CI/schema generation, plugins, localization.

## 2. CLI contract

### 2.1 Global invocation

```text
syntagmax [global-options] command [command-options]
```

Global options:

- `--cwd PATH` → `chdir` before command execution.
- `-f/--config-file PATH` → project TOML; default `.syntagmax/config.toml`.
- `--log {debug,info,warning,error,silent}` → console verbosity.
- `--warnings-as-errors/--no-warnings-as-errors` → convert collected warnings to fatal result.
- `--render-tree` → include artifact tree in analysis report.
- `--no-git` → skip Git revision population.
- `--lang {en,ru}` → report language override.

### 2.2 Commands

| Command | Behavior rule |
|---|---|
| `init` | Create `.syntagmax/config.toml` and `.syntagmax/project.syntagmax` scaffold. |
| `analyze [STEP]` | Load config; execute dependency closure for `STEP`; render one report. Default step: `metrics`. |
| `publish RECORD...` / `publish --all` | Extract configured records into blocks and render Markdown. `--single` consolidates output. |
| `edit identification` | Assign/repair artifact IDs from metamodel schema; supports `--all`, `--atype`, `--force`, `--dry-run`. |
| `edit attrs` | Bulk add/delete/replace YAML attributes or inline fields; supports CSV lookup and dry run. Obsidian driver only. |
| `edit markers renumber` | Assign sequential IDs to unmarked fragment blocks. |
| `trace --child TYPE --parent TYPE` | Export traceability matrix, optionally via configured plugins. |
| `change report --base REV` | Compare revisions; supports consolidated and summary output. |
| `change baseline TAG` | Create a baseline tag across affected repositories. |
| `ai verify TASK.md` | Invoke an AI agent for an open `TASK-IMPACT-*` task; validate the task result and optional child amendment. |
| `mcp run CONFIG` | Initialize analyzed artifact graph and expose MCP read tools. |
| `schema` / `ci` | Generate JSON schemas / CI workflow configuration. |

### 2.3 Exit behavior

- `0` → success.
- `1` → `FatalError` / user-correctable fatal condition.
- `2` → domain/RMS processing error.
- `3` → unexpected exception with traceback.
- `ai verify` uses a separate operational meaning: exit `0` can mean verified/closed **or** validly requires more work.

## 3. Configuration rules

- Read global config first (`SYNTAGMAX_HOME/config.toml`, else `~/.config/syntagmax/config.toml`), then merge project TOML over it.
- Config file directory = root for config-relative paths; `base` selects the artifact/project base directory.
- Required top-level data: `[[input]]`; optional sections include `metrics`, `impact`, `metamodel`, `publish`, `plugin`, `drivers`, `trace`, `ai`, `report`, `baseline`.
- Input record fields determine: source directory, driver, default artifact type, marker(s), glob filter, publish config, exclusions, and task template.
- Driver default globs include: `obsidian/**/*.md`, `markdown/**/*.md`, `simple-markdown/**/*.md`, `ipynb/**/*.ipynb`; explicit `filter` overrides the default.
- `output_path` defaults to `outputs/`, resolved relative to config root; analysis report defaults to `<output_path>/report.md`.
- Publish config precedence: per-record config → global publish config → built-in defaults.
- Invalid TOML, missing referenced files, invalid enum/value, duplicate exclusion, bad path, or invalid metamodel → `FatalError` before useful processing.

## 4. Analysis pipeline

### 4.1 Dependency DAG

```text
extract
  → build_artifact_map
    → populate_pids
      → build_tree
        → tree (= analyse_tree)
          → metrics

build_artifact_map → populate_revisions
build_tree + populate_revisions → impact
```

Rules:

- Requested public targets: `extract`, `tree`, `impact`, `metrics`.
- `process()` calculates the transitive dependency closure and runs each step once in execution order.
- `--no-git` skips `populate_revisions`; impact still depends conceptually on revision data and may report limitations/errors.
- Any missing intermediate (`artifacts_list` or artifact map) is an internal fatal error.
- Metrics are calculated globally and per contributing input record when more than one record contains the configured requirement type.
- If impact task generation is enabled, impact post-processing writes tasks to configured `tasks_dir` (default `tasks/`).
- `--render-tree` adds tree text only when a `ROOT` artifact exists.

### 4.2 Extraction and identity

- `extract()` selects extractor by `InputRecord.driver`: `text`, `sidecar`, `obsidian`, `ipynb`, `simple-markdown`.
- Each extractor returns artifacts plus extraction errors; errors are attached to the input/category in the report.
- `build_artifact_map()` rejects/records artifacts with no ID or `UNDEFINED_ID`.
- Duplicate artifact IDs are rejected/recorded; first map entry is retained.
- Artifact identity = `aid`; artifact type = `atype`; mandatory semantic body field = `contents`.
- Git-backed artifacts may receive line/file revisions for traceability and impact analysis.

### 4.3 Metamodel DSL

```text
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute parent is optional reference to parent
trace from REQ to SYS is mandatory via commit
```

Rules:

- Lark parses artifact definitions, `id` rules, typed attributes, conditional attributes, and trace rules.
- `id` is a special rule; a regular attribute named `id` is invalid.
- Every artifact type must define a non-conditional mandatory `id` rule and a non-conditional mandatory `contents` rule.
- Supported value families include string, integer, boolean (including custom true/false values), enum, reference, and multiple values.
- Conditional rules require an existing non-conditional boolean anchor in the same artifact definition.
- ID schemas may contain at most one `{num}` macro.
- Metamodel violations fail early; parsed model drives extraction/validation/editing behavior.

## 5. Validation, tree, and impact

- `populate_pids()` resolves parent references; `build_tree()` constructs the artifact hierarchy and trace relationships.
- Tree analysis validates artifact attributes, references, multiplicity, conditional rules, and trace obligations.
- Git revisions identify changed lines/files; suspicious or outdated parent-child links feed impact analysis.
- Impact can generate one task per affected relationship using `src/syntagmax/resources/task.j2` and configured type mapping.
- Report sections are ordered approximately: errors → tree → metrics → impact → AI analysis.
- Warning handling is global; with warnings-as-errors, collected warnings become fatal at command completion.

## 6. Publishing pipeline

```text
select records
→ extract files into BlockTree
→ deterministic IDs for anonymous marked text blocks
→ duplicate explicit block-ID check
→ pre block plugins / optional named filter
→ render artifacts + text + images
→ post Markdown plugins
→ write .md
→ optional Pandoc .docx/.pdf
```

Rules:

- `publish` requires record names or `--all`; `--single` and `--date-suffix` are mutually exclusive.
- Separate mode writes one file per record; single mode writes `publish/published.md` by default.
- Anonymous marked text blocks receive an 8-character SHA-256-derived ID from marker + path + content.
- Explicit block IDs are unique per marker type; duplicate IDs become publish errors.
- Rendering is config-driven; fallback output emits heading, contents, then sorted metadata table.
- Attribute presence modes control metadata visibility; field matching/exclusions are case-insensitive where implemented.
- Image references are resolved/copied to `images/`; remote URLs and fenced-code references remain unchanged.
- Plugins run in configured order; wrong hook return types are fatal.
- Missing Pandoc does not prevent Markdown output; DOCX/PDF conversion is skipped/warned.

## 7. Editing and AI rules

- Identification preserves valid IDs unless `--force`; new IDs start after the maximum valid number per artifact type.
- `--dry-run` reports planned edits without writing source files.
- `ai verify` rejects `--agent` + `--command`; custom command must contain `{prompt}`.
- Only open `TASK-IMPACT-*` tasks are processed; non-open tasks exit without verification.
- Agent exit nonzero aborts; task frontmatter is validated after the agent; amended child artifacts receive integrity validation.
- AI provider logs are intended to redact sensitive headers, bodies, and URLs.

## 8. MCP read model

- Server initializes extraction → artifact map → parent IDs → tree → analysis before serving.
- Initialization errors prevent server startup.
- Tools: `list_artifacts`, `search_artifacts`, `get_artifact_content`.
- Search is case-insensitive substring matching over ID, type, and field values.
- Artifact content includes location, latest revision, parents/children, fields, and body; `ROOT` is hidden from list/search presentation.

## 9. Approved format decisions

- **Style:** retain compact rule lists, tables, diagrams, and short code blocks.
- **Coverage:** enumerate every public CLI option and every configuration field, including defaults, precedence, validation, and side effects.
- **Organization:** group implementation details by subsystem; do not make the document primarily file-by-file.
- **Evidence status:** mark behavior inferred from code but not confirmed by tests/docs as `UNVERIFIED`.
- **Final filename:** `SYNTAGMAX_APPLICATION_LOGIC.md`.
- **Current artifact:** this file remains the review draft until the full document is generated under the final filename.

## 10. Full-version expansion contract

- **CLI subsystem:** audit every command, subcommand, positional argument, option, default, mutual exclusion, validation branch, output, and exit code.
- **Configuration subsystem:** list every TOML field and nested field; document type, default, path base, merge precedence, coercion, validation, and runtime consumers.
- **Analysis subsystem:** document the complete DAG, intermediate data shapes, dependency closure, skipped steps, error accumulation, report assembly, and task generation.
- **Extraction subsystem:** cover every driver, file filter, marker format, frontmatter/YAML behavior, heading splitting, sidecars, notebooks, text blocks, and `contents` rules.
- **Metamodel subsystem:** cover grammar, artifact/attribute types, ID schemas, conditions, references, multiplicity, traces, validation errors, and boolean coercion.
- **Tree/validation subsystem:** cover parent resolution, root construction, trace checks, suspicious links, metrics, revisions, and impact decisions.
- **Publishing subsystem:** cover block-tree construction, record selection, rendering configuration, fallback rendering, attribute presence, plugins, images, output naming, and Pandoc behavior.
- **Editing subsystem:** cover identification, attribute operations, marker renumbering, preservation rules, force/dry-run behavior, and source-file mutations.
- **Change/CI/schema subsystem:** cover change reports, baselines, localization, schema generation, and CI workflow generation.
- **AI/MCP subsystem:** cover agent registry/command execution, prompt construction, validation, amendment rules, server initialization, tools, and search semantics.
- **Testing/evidence:** cross-check each rule against focused tests and source locations; label unresolved or test-only claims `UNVERIFIED`.
