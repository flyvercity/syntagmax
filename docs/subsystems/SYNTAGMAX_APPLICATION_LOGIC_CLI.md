# Syntagmax Application Logic — CLI Subsystem

> **Step 2 subsystem document.** Scope is the Click command surface and command orchestration only. Configuration schema, extraction internals, analysis algorithms, publishing renderer internals, and AI/MCP implementation details are referenced only where the CLI invokes them.
>
> **Evidence:** `src/syntagmax/cli.py`, `cli_publish.py`, `cli_edit.py`, `cli_change.py`, `cli_tools.py`, `cli_ai.py`, `init_cmd.py`, `utils.py`, `params.py`, plus focused CLI tests. Claims marked `UNVERIFIED` are not confirmed by a focused test or require runtime/environment confirmation.

## 1. CLI architecture

### 1.1 Entry point

- Package script: `syntagmax = syntagmax.cli:main`.
- Root Click group: `rms` (`src/syntagmax/cli.py`).
- Root group registers:
  - direct commands: `init`, `analyze`, `publish`, `trace`;
  - command groups: `change`, `edit`, `mcp`, `schema`, `ci`, `ai`.
- `main()` catches application exceptions after Click dispatch:
  - `FatalError` → red message, process exit `1`;
  - `RMSException` → red message, process exit `2`;
  - other `Exception` → red message + traceback, process exit `3`.
- Explicit `SystemExit` from command handlers is preserved.
- Click parsing/usage errors are handled by Click itself; exact exit/output is `UNVERIFIED` here.

### 1.2 Invocation model

```text
syntagmax [ROOT_OPTIONS] COMMAND [COMMAND_OPTIONS] [ARGS]
```

Execution order:

1. Click parses root options and command arguments.
2. `rms()` configures Rich logging before project configuration is loaded.
3. `Params` is created from root option values and stored in `ctx.obj`.
4. If `--cwd` is supplied, the process changes directory immediately.
5. The selected command loads configuration or constructs `Config` directly.
6. Command-specific orchestration runs; errors are printed or raised.
7. The root result callback collects warnings and raises `FatalError` when warnings-as-errors is active.

## 2. Root options and global behavior

### 2.1 Root options

| Syntax | Type/default | Behavior |
|---|---|---|
| `--version` | Click version option | Prints installed package version and exits. Version comes from package metadata. `UNVERIFIED`: exact output format. |
| `--log LEVEL` | choice: `debug`, `info`, `warning`, `error`, `silent`; default `None` | CLI value controls initial Rich/root log level; if absent, config/default resolution supplies the effective level. CLI overrides project config. |
| `--warnings-as-errors/--no-warnings-as-errors` | boolean; default `None` | Explicit `true` installs a warning collector before command execution. Explicit `false` disables config-level warnings-as-errors behavior at result handling. |
| `--render-tree` | flag; default `false` | Requests tree rendering in analysis reports. Stored in `Params`. |
| `--cwd PATH` | existing path; default `None` | Changes working directory before command execution. Relative config paths and generated files are then resolved from the new directory. |
| `--no-git` | flag; default `false` | Requests skipping Git history extraction in analysis. Stored in `Params`. Commands that need Git may still fail or use their own Git path. |
| `--lang LANGUAGE` | choice: `en`, `ru`; default `None` | CLI language override, stored as `language`; configuration resolution decides the effective report locale. |
| `-f PATH`, `--config-file PATH` | path; default `.syntagmax/config.toml` | Global project configuration path. Stored in `Params` as `config_file`; most commands consume this value. |

### 2.2 Logging rules

- Initial CLI level is `INFO` when `--log` is absent.
- `--log debug` enables debug diagnostics, including configuration details.
- `--log silent` suppresses log messages, but command-generated output/errors may still be printed.
- Project `log_level` is applied after config loading unless overridden by `--log`.
- `--warnings-as-errors` installs `WarningsAsErrorsHandler` at root setup.
- Config-level warnings-as-errors is applied during config loading.
- At result callback, any collected warning plus active warnings-as-errors raises `FatalError`.
- Tested behavior: default info, config override, CLI override, silent mode, warning promotion, and `--no-warnings-as-errors` override are covered by `tests/test_cli_log_level.py`.

### 2.3 Config-file option duplication

- Root `-f/--config-file` is available before the command.
- `publish`, `trace`, and `edit attrs` redeclare a command-local `-f/--config-file`.
- `edit identification`, `edit markers renumber`, and `mcp run` use their own config argument.
- `analyze`, `change`, and `ai` consume the root `Params['config_file']`.
- `schema` does not load a project config.
- `ci` does not load a project config.
- `UNVERIFIED`: whether users should rely on placing `-f` before versus after a command for every nested command; Click accepts the locations only where that command declares the option.

## 3. `init`

### 3.1 Syntax

```text
syntagmax [ROOT_OPTIONS] init
```

No command-local options or arguments.

### 3.2 Logic

1. Read root `cwd` from `ctx.obj`.
2. Call `init_project(cwd)`.
3. Use `cwd` if supplied; otherwise use the current process directory.
4. Create `.syntagmax/` if absent; existing directory is reused.
5. Always write/overwrite:
   - `.syntagmax/config.toml` generated from Pydantic config models;
   - `.syntagmax/project.syntagmax` with a minimal `SYS` artifact model;
   - `.syntagmax/.gitignore` containing `reports/`.
6. Print a green initialization message.

### 3.3 Generated scaffold decisions

- Generated TOML includes commented defaults for global, metrics, impact, baseline, and AI settings.
- It creates one active input record named `requirements`, directory `REQ`, driver `obsidian`.
- It creates a metamodel with mandatory `id` and `contents` for `SYS`.
- `UNVERIFIED`: `init` does not prompt before overwriting existing scaffold files; this follows the implementation but lacks a dedicated CLI integration test.
- Tests: `tests/test_init_cmd.py` verifies `cwd`, current-directory mode, existing `.syntagmax/`, generated config, and generated metamodel.

## 4. `analyze`

### 4.1 Syntax

```text
syntagmax [ROOT_OPTIONS] analyze [ANALYZE_OPTIONS] [STEP]
```

`STEP` is optional and restricted to the public steps returned by `public_steps()`:

```text
extract | tree | impact | metrics
```

Default: `metrics`.

### 4.2 Options

| Syntax | Type/default | Behavior |
|---|---|---|
| `--allow-dirty-worktree` | flag; `false` | Store permission to analyze a dirty Git worktree in `Params`. The enforcement is downstream. |
| `--suppress-tracing` | flag; `false` | Store tracing-error suppression request in `Params`; analysis layer decides its effect. |
| `--tasks` | flag; `false` | Store task-generation override in `Params`; config/impact layer consumes it. |
| `--output VALUE` | string; default `None` | `None` → `<config.output_dir()>/report.md`; `console` → print Markdown; otherwise create parent and write the specified file. |

### 4.3 Logic

1. Copy `allow_dirty_worktree`, `suppress_tracing`, and `tasks` into `Params`.
2. Load project config through `load_config_or_exit()`.
3. Call `process(step, config)`.
4. Render the returned `Report` to Markdown.
5. Write to the selected output or print to stdout.
6. For file output, print success in green or warning in yellow when report errors exist.
7. Report error count does not itself cause a nonzero exit; fatal/config exceptions do.

### 4.4 CLI-level decisions

- Dependency resolution is delegated to `main.process`; CLI only selects the public target.
- `--no-git`, `--render-tree`, language, logging, and config path are root options, not analyze-local options.
- `--output console` is a literal sentinel, not a path.
- `UNVERIFIED`: exact handling of `allow_dirty_worktree` and `suppress_tracing` requires tracing the downstream analysis modules.

## 5. `publish`

### 5.1 Syntax

```text
syntagmax [ROOT_OPTIONS] publish [PUBLISH_OPTIONS] [RECORD ...]
```

The command requires either one or more record names or `--all`.

### 5.2 Options and argument

| Syntax | Type/default | Behavior |
|---|---|---|
| `RECORD ...` | zero or more strings | Names of configured input records to publish. Validated against loaded records. |
| `--all` | flag; `false` | Select all configured input records. |
| `--single` | flag; `false` | Consolidate selected records into one Markdown output. |
| `--output PATH` | path; default `None` | `--single`: default `<output_dir>/publish/published.md`; separate mode: default `<output_dir>/publish/`. Explicit value is file-like in single mode and directory-like in separate mode. |
| `-f/--config-file PATH` | path; default `.syntagmax/config.toml` | Command-local config path passed to `load_config_or_exit()`. |
| `--date-suffix` | flag; `false` | Separate mode only; append `YYYY-MM-DD` to each record filename. Reject with `--single`. |
| `--docx` | flag; `false` | Request Pandoc DOCX conversion after Markdown generation. |
| `--pdf` | flag; `false` | Request Pandoc PDF conversion after Markdown generation. |
| `--docx-template PATH` | string; default `None` | CLI override for DOCX reference document; `none` disables the template. Missing explicit file raises `FatalError`. |
| `--pre-filter NAME` | string; default `None` | Find and run one configured pre-publishing block-filter plugin. |

### 5.3 Common validation

- No records and no `--all` → red error, `sys.exit(1)`.
- `--single` + `--date-suffix` → red error, `sys.exit(1)`.
- Named record absent from config → red error, `sys.exit(1)`.
- Config path absent → `load_config_or_exit()` prints an error and exits `1`.
- Pandoc requested but unavailable → warning; Markdown generation continues.

### 5.4 Single-output path

1. Build a block tree for configured inputs.
2. Print block errors in red but continue through rendering.
3. Keep only selected records.
4. Run configured block transforms.
5. Run optional named pre-filter.
6. Render Markdown and collect image manifest.
7. Run Markdown transforms.
8. Create output parent and write one file.
9. Remove stale output images and copy manifest images.
10. Print artifact/text-block counts.
11. If Pandoc is available, resolve DOCX template and convert requested formats.
12. In multi-record single mode, conflicting per-record DOCX templates produce a warning; first template wins.
13. Conversion failure causes `sys.exit(1)` after Markdown already exists.

### 5.5 Separate-output path

1. Create output directory.
2. For each selected record, rebuild the block tree and retain that record.
3. Run block transforms, optional pre-filter, rendering, and Markdown transforms.
4. Sanitize record name by replacing `/` and `\\` with `_`.
5. Reject empty, `.` or `..` safe names with `sys.exit(1)`.
6. Write `<record>.md` or `<record>_YYYY-MM-DD.md`.
7. Merge all image manifests and copy images before conversion.
8. Convert each published file when Pandoc is available.
9. Any conversion failure causes `sys.exit(1)` after Markdown files exist.

### 5.6 Output/format decisions

- `--docx-template none` is a supported explicit no-template value.
- A missing explicit DOCX template is fatal.
- Missing Pandoc is nonfatal; conversion is skipped.
- Image-copy cleanup removes existing files directly under output `images/`; missing sources produce warnings.
- Tests: `tests/test_cli_publish.py` covers basic separate/single output, date suffix, invalid combinations, missing records/config, missing Pandoc, invalid record names, template `none`, and missing templates.
- `UNVERIFIED`: exact behavior when a block plugin returns invalid data is implemented downstream and not covered by this CLI document.

## 6. `trace`

### 6.1 Syntax

```text
syntagmax [ROOT_OPTIONS] trace [TRACE_OPTIONS]
```

### 6.2 Options

| Syntax | Type/default | Behavior |
|---|---|---|
| `--child TYPE` | required string | Child artifact type. |
| `--parent TYPE` | required string | Parent artifact type. |
| `--forward/--reverse` | boolean; default `forward` | Forward = child→parent; reverse = parent→child. |
| `--attribute NAME` | repeatable string; default empty tuple | Add lead-artifact fields as trace columns. |
| `--flat` | flag; `false` | Combine multiple linked IDs into semicolon-separated values. |
| `--delimiter VALUE` | string; default `None` | Explicit separator; literal `\\t` is converted to a tab. |
| `--output VALUE` | string; default `None` | `console` prints; otherwise writes file. Default is a dated file under `<output_dir>/trace/`. |
| `-f/--config-file PATH` | path; default `.syntagmax/config.toml` | Command-local config path. |

### 6.3 Logic

1. Load config.
2. Manually run extraction → artifact map → parent resolution → tree build.
3. Print pipeline errors as yellow warnings; do not immediately abort.
4. Warn if child or parent type is not defined in the loaded metamodel.
5. Build the trace matrix with requested direction, attributes, and flat mode.
6. If trace plugins are configured, run all configured trace-export plugins sequentially and do not execute the built-in file-rendering branch.
7. Otherwise select delimiter:
   - explicit `--delimiter` if supplied;
   - tab for `.tsv` output path;
   - comma otherwise.
8. Default filename uses direction and current date: `trace-<from>-<to>-YYYY-MM-DD.csv|tsv`.
9. Print to stdout for `--output console`; otherwise create parent and write text.

`UNVERIFIED`: exact plugin output contract and behavior when pipeline warnings coexist with a generated matrix require plugin/trace tests.

## 7. `change`

## 7.1 Group

```text
syntagmax [ROOT_OPTIONS] change report ...
syntagmax [ROOT_OPTIONS] change baseline TAG ...
```

The group itself has no options.

### 7.2 `change report`

#### Options

| Syntax | Type/default | Behavior |
|---|---|---|
| `--base REV` | required string | Base Git commit/tag/branch/`HEAD`/`HEAD~N`/`working`. |
| `--target REV` | required string | Target Git revision or `working`. |
| `--output VALUE` | string; default `None` | `console` prints; otherwise output directory/file logic applies. Default `<output_dir>/change/`. |
| `--include-non-artifact` | flag; `false` | Include changed non-artifact text blocks. |
| `--single` | flag; `false` | Consolidate per-record reports into one file. |
| `--summary` | flag; `false` | Use abbreviated summary renderer without content. |

#### Logic

1. Load config from root `Params['config_file']`.
2. Open the Git repository containing `config.base_dir()`.
3. Run Git version, input-record location, and worktree-ignore preflight checks.
4. Create/use `<config_root>/worktrees` for paired revisions.
5. Resolve base and target revisions; warn when equal non-working revisions are selected.
6. Determine changed files or working-tree changes.
7. Extract blocks at both revisions.
8. For extraction failures, read available source files and generate a unified fallback diff.
9. Filter changes by input record.
10. Compare artifacts, sidecar/binary artifacts, and optionally text blocks.
11. Render detailed or summary Markdown for each record.
12. If no record names are produced, print a yellow no-change message and return normally.
13. Output modes:
    - `console`: print each report, adding filename separators for multiple reports;
    - `--single`: write one consolidated file, generating a name when output is directory-like;
    - otherwise: write one dated file per record.

Filename pattern:

```text
<safe-record>-<base7>-to-<target7>-YYYYMMDD[-summary].md
change-<base7>-to-<target7>-YYYYMMDD[-summary].md
```

`working` is used as the revision label instead of a hash.

`UNVERIFIED`: worktree cleanup guarantees and exact behavior under partial extraction failure require the change integration suite.

### 7.3 `change baseline`

#### Syntax and options

```text
syntagmax [ROOT_OPTIONS] change baseline TAG_NAME [OPTIONS]
```

| Syntax | Type/default | Behavior |
|---|---|---|
| `TAG_NAME` | required string | Tag to create in every discovered repository. |
| `-m/--message TEXT` | string; default `Baseline created by Syntagmax` | Annotated-tag message. |
| `--force` | flag; `false` | Permit overwriting an existing tag. |
| `--dry-run` | flag; `false` | Validate and print plan without creating tags. |

Logic:

1. Load config.
2. Discover Git repositories containing configured input records.
3. Fail if no repositories, a record is outside the base directory, or a record is not in a repository.
4. Require clean repositories, including no untracked/staged/modified files.
5. Validate tag against configured `baseline.tag_pattern` using full matching.
6. Reject an existing tag unless `--force`.
7. Dry run prints tag, message, repository count, and each HEAD short hash; no tag is created.
8. Normal mode creates annotated tags across repositories.
9. On success, print repository/commit pairs and shell commands the user can run to push tags. The CLI does not push.
10. Tag creation rollback on a later repository failure is delegated to `create_baseline_tag()`.

Tests: `tests/test_change_baseline.py` covers discovery, clean-state checks, tag validation/existence, force, rollback, single/multi-repository CLI paths, and dry-run-related behavior in the implementation.

## 8. `edit`

### 8.1 `edit identification`

```text
syntagmax [ROOT_OPTIONS] edit identification [CONFIG_PATH] [OPTIONS]
```

| Syntax | Type/default | Behavior |
|---|---|---|
| `CONFIG_PATH` | existing path; default `.syntagmax/config.toml` | Positional config path. |
| `--all` | flag; `false` | Process all artifacts. |
| `--atype TYPE` | string; default `None` | Restrict processing to one artifact type. |
| `--force` | flag; `false` | Renumber all from `1`, ignoring valid existing IDs. |
| `--dry-run` | flag; `false` | Calculate/report edits without writing. |

Rules:

- Require `--all` or `--atype`; otherwise print error and exit `1`.
- Both may be supplied; `atype` remains available as a filter to the implementation.
- Load config using the positional path.
- Call `renumber_artifacts(config, atype, dry_run, force)`.
- If it returns false, exit `1`; otherwise return normally.

### 8.2 `edit attrs`

```text
syntagmax [ROOT_OPTIONS] edit attrs [OPTIONS]
```

| Syntax | Type/default | Behavior |
|---|---|---|
| `-f/--config-file PATH` | existing path; `.syntagmax/config.toml` | Command-local config. |
| `-o/--operation` | `add`, `del`, `replace`; default `add` | Attribute mutation operation. |
| `-t/--type` | `attr`, `field`; default `attr` | Target YAML attribute or inline field. |
| `-n/--name NAME` | string; default `None` | Attribute/field name. Omit for metamodel-driven add. |
| `-l/--value VALUE` | string; default `None` | Value; metamodel-driven add defaults downstream, documented as `TBD`. |
| `-s/--section NAME` | required string | Input record name. |
| `--csv PATH` | existing path; default `None` | Optional ID-to-value mapping source. |
| `--csv-id-column NAME` | string; `id` | CSV artifact-ID column. |
| `--csv-value-column NAME` | string; `value` | CSV replacement-value column. |
| `-d/--csv-delimiter VALUE` | string; `,` | CSV delimiter. |
| `--dry-run` | flag; `false` | Preview without writing. |

Validation branches:

- `del` or `replace` without `--name` → print error and return; no explicit nonzero exit.
- `add` with a value but no name → print error and return.
- `replace` without `--value` and without `--csv` → print error and return.
- Otherwise load config, optionally load CSV mapping, and call `manipulate_attributes()`.
- `UNVERIFIED`: validation-error return paths likely exit `0` because they return without raising; no focused exit-code test found.

### 8.3 `edit markers renumber`

```text
syntagmax [ROOT_OPTIONS] edit markers renumber [CONFIG_PATH] [OPTIONS]
```

| Syntax | Type/default | Behavior |
|---|---|---|
| `CONFIG_PATH` | existing path; `.syntagmax/config.toml` | Positional config path. |
| `--all` | flag; `false` | Renumber across all input records. |
| `--section NAME` | string; `None` | Restrict to one input record. |
| `--marker TYPE` | string; `None` | Restrict to one marker type. |
| `--dry-run` | flag; `false` | Print planned changes without writing. |

Rules:

- Neither `--all` nor `--section` → print error and return.
- Both `--all` and `--section` → print error and return.
- Otherwise load config and call `renumber_markers()`.
- `UNVERIFIED`: validation-error return paths likely exit `0`; no focused exit-code test found.

## 9. `ai verify`

### 9.1 Syntax and options

```text
syntagmax [ROOT_OPTIONS] ai verify TASK_FILE [OPTIONS]
```

| Syntax | Type/default | Behavior |
|---|---|---|
| `TASK_FILE` | existing path; required | Impact task to verify. |
| `--agent NAME` | string; `None` | Override configured AI agent. |
| `--command PATTERN` | string; `None` | Ad-hoc command; must contain `{prompt}`. Mutually exclusive with `--agent`. |
| `--amend` | flag; `false` | Permit direct child-artifact amendment when verification fails. |

### 9.2 Logic

1. Reject simultaneous `--agent` and `--command` with exit `1`.
2. Load config using root `Params['config_file']`.
3. Parse task frontmatter/content.
4. Reject task IDs not beginning `TASK-IMPACT-` with exit `1`.
5. If status is not `open`, print a yellow no-op message and exit `0`.
6. Warn if the repository is dirty; do not abort solely for dirty state.
7. Resolve parent and child artifact paths from task record/path data.
8. Agent selection:
   - `--command`: create a custom agent config and bypass registry lookup;
   - otherwise use `--agent` or configured `ai.agent`, then resolve registry entry.
9. Render the verification prompt, including amendment mode.
10. Invoke the agent in the configured base directory.
11. Nonzero agent exit → print abort message and exit `1`.
12. Validate task output/frontmatter; invalid output → exit `1`.
13. Re-read final task status and detect `### Amendment Applied`.
14. If `--amend` and amendment marker exist, validate child artifact integrity.
15. Output:
   - closed without amendment → verified/closed;
   - closed with valid amendment → verified and child amended, with `git diff` hint;
   - otherwise → requires more work, but no explicit nonzero exit.

Tests: `tests/test_cli_ai.py` covers amendment/no-amendment, child validation failure, valid/invalid custom command, mutual exclusivity, and success messages.

`UNVERIFIED`: exact behavior for unknown configured agents and malformed task files depends on lower-level parser/registry exceptions.

## 10. `mcp run`

### Syntax

```text
syntagmax [ROOT_OPTIONS] mcp run CONFIG_PATH [OPTIONS]
```

| Syntax | Type/default | Behavior |
|---|---|---|
| `CONFIG_PATH` | existing path; required | Configuration passed directly to `Config`. |
| `--host HOST` | string; `127.0.0.1` | MCP SSE host. |
| `--port PORT` | inferred integer; `8000` | MCP SSE port. |
| `--sse-path PATH` | string; `/` | SSE stream path. |
| `--transport` | choice `stdio`/`sse`; `stdio` | MCP transport. |

Logic:

- Construct `Config(obj, Path(config_path))` directly rather than using `load_config_or_exit()`.
- Call `run_mcp_server(config, host, port, sse_path, transport)`.
- Server initialization and artifact analysis occur downstream before serving.
- `UNVERIFIED`: exact process lifetime and transport error exit behavior require MCP integration tests.

## 11. `schema`

### Syntax

```text
syntagmax schema publish
syntagmax schema config
```

No arguments or options.

- `schema publish` calls `PublishConfig.model_json_schema()` and prints indented JSON to stdout.
- `schema config` calls `ConfigFile.model_json_schema()` and prints indented JSON to stdout.
- Neither command loads a project or global configuration.
- `UNVERIFIED`: schema ordering and exact JSON formatting are source-derived but not covered by a focused CLI test.

## 12. `ci`

### 12.1 Group option

```text
syntagmax [ROOT_OPTIONS] ci [--target github|gitlab] install COMMAND
```

| Syntax | Type/default | Behavior |
|---|---|---|
| `--target PLATFORM` | choice `github`, `gitlab`; `github` | Stores target in Click context object for nested install commands. |

### 12.2 `ci install analyze`

- GitHub output: `.github/workflows/syntagmax-analyze.yml`.
- GitLab output: `.gitlab-ci.yml`.
- Generated workflow installs Syntagmax using `uv`, runs `syntagmax analyze`, and publishes `.syntagmax/outputs/report.md` as an artifact.
- GitHub workflow uses `workflow_dispatch`, read-only contents permission, checkout, setup-uv, installation, analysis, artifact upload.
- GitLab job uses web-trigger rule, Python 3.13 image, installs `curl`/`uv`, installs Syntagmax, runs analysis, stores the report.

### 12.3 `ci install publish`

- GitHub output: `.github/workflows/syntagmax-publish.yml`.
- GitLab output: `.gitlab-ci.yml`.
- Generated workflow runs `syntagmax publish --all --single` and publishes `.syntagmax/outputs/publish/published.md`.
- GitHub and GitLab generated content differs only in platform syntax and setup commands.
- Existing target files are overwritten by `write_text()`; `UNVERIFIED`: no overwrite confirmation is implemented.
- Tests: `tests/test_ci_commands.py` covers GitHub/GitLab targets, default GitHub target, generated file paths/content, and root `--cwd` behavior.

## 13. Command-to-source map

| CLI surface | Primary implementation | Main downstream call |
|---|---|---|
| root/options/error handling | `src/syntagmax/cli.py` | logging, `Params`, `process()` |
| `init` | `src/syntagmax/cli.py`, `init_cmd.py` | `init_project()` |
| `analyze` | `cli.py` | `main.process()` and `Report.render()` |
| `publish` | `cli_publish.py` | block tree, plugins, renderer, Pandoc |
| `trace` | `cli_tools.py` | extraction, tree, trace matrix/export |
| `mcp run` | `cli_tools.py` | `run_mcp_server()` |
| `schema` | `cli_tools.py` | Pydantic JSON schema generation |
| `ci` | `cli_tools.py` | workflow file generation |
| `change` | `cli_change.py` | worktrees, extraction, diff, rendering, tagging |
| `edit` | `cli_edit.py` | ID, attribute, and marker mutation modules |
| `ai verify` | `cli_ai.py` | task parser, agent registry/invocation, validators |
| config existence guard | `src/syntagmax/utils.py` | `load_config_or_exit()` |
| root parameter shape | `src/syntagmax/params.py` | TypedDict keys consumed by commands |

## 14. CLI invariants and risk points

- Root options must be parsed before command execution; `--cwd` changes the resolution context for later relative paths.
- Commands that mutate files/tags do not generally provide a common confirmation layer; dry-run support is command-specific.
- `edit attrs` and `edit markers renumber` validation failures return after printing rather than explicitly exiting nonzero; this is a CLI contract risk and is marked `UNVERIFIED` at integration level.
- `publish` writes Markdown before optional Pandoc conversion, so conversion failure can leave valid Markdown artifacts behind.
- `change baseline` performs cross-repository validation and relies on downstream rollback for partial tag creation.
- `trace` can print pipeline errors as warnings and still build/export a matrix.
- `schema` and CI commands intentionally operate without project configuration loading.
- The CLI layer delegates most semantic validation to downstream modules; this document records the delegation boundary rather than duplicating those subsystem specifications.

## 15. Evidence status

- **Confirmed by source:** command registration, decorator options/defaults, dispatch order, validation branches, output paths, generated CI filenames, exception mapping.
- **Confirmed by focused tests:** initialization, logging/warnings-as-errors, publishing, AI amendment/custom command behavior, CI generation, baseline integration and helpers.
- **`UNVERIFIED`:** exact Click-generated help/version formatting, all trace/schema/MCP CLI error paths, downstream effects of analyze-only flags, plugin failure output through CLI, and lower-level malformed-input exception messages.
