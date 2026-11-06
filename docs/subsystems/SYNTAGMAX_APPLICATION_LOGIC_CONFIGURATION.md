# Syntagmax Application Logic — Configuration Subsystem

> **Step 2 subsystem document.** This document describes configuration loading, models, defaults, path resolution, validation, precedence, and runtime state construction. It covers the main TOML configuration and publish configuration files. CLI parsing is documented separately in `SYNTAGMAX_APPLICATION_LOGIC_CLI.md`.
>
> **Evidence:** `src/syntagmax/config.py`, `publish_config.py`, `plugin.py`, `obsidian_settings.py`, `init_cmd.py`, `utils.py`, `docs/reference/configuration.md`, `docs/reference/paths.md`, and focused tests. `UNVERIFIED` marks behavior inferred from a source/docs boundary or not covered by a focused test.

## 1. Configuration layers and terminology

| Layer | Meaning | Typical location/base |
|---|---|---|
| CWD | Process working directory; can be changed by CLI `--cwd`. | command invocation directory |
| Config root | Parent directory of the selected TOML file. | `.syntagmax/` by default |
| Base directory | Source repository/vault root from `base`. | config root + `base` |
| Input directory | One configured source root from `[[input]].dir`. | base + `dir` |
| Global config | Optional defaults loaded before project config. | `$SYNTAGMAX_HOME/config.toml` or `~/.config/syntagmax/config.toml` |
| Project config | Primary TOML file. | `.syntagmax/config.toml` by default |
| Publish config | Rendering model loaded separately. | per-record, global, auto-discovered, or defaults |
| Runtime `Config` | Validated model plus resolved records, metamodel, plugins, and derived paths. | in memory |

Core rule:

```text
Global TOML → project TOML merge → CLI precedence → Pydantic validation
→ path/record/metamodel/plugin resolution → runtime Config
```

## 2. Load algorithm

`Config(params, config_filename)` performs these stages:

1. Set `_root_dir` to the absolute parent of `config_filename`.
2. Initialize runtime defaults for metrics, impact, report, output path, records, and plugins.
3. Locate global config:
   - if `SYNTAGMAX_HOME` is set: `$SYNTAGMAX_HOME/config.toml`;
   - otherwise: expanded `~/.config/syntagmax/config.toml`.
4. If global config exists, parse TOML and merge it first.
5. Read and merge project TOML over global values.
6. Resolve logging and warnings-as-errors early to prevent unwanted log leakage.
7. Validate merged data as `ConfigFile` with Pydantic.
8. Resolve base directory and global publish settings.
9. Materialize input records and their file lists.
10. Emit the misplaced per-record publish warning when applicable.
11. Store metrics, impact, AI, report, driver, baseline, trace, and output settings.
12. Apply CLI `--tasks` override if present.
13. Resolve language and initialize i18n.
14. Validate Obsidian strict-line-breaks constraints.
15. Load the metamodel when configured; otherwise warn and use `None`.
16. Validate fragment-marker/attribute collisions.
17. Inject task metamodel definitions when task generation is enabled.
18. Raise accumulated errors as `FatalError`.
19. Load enabled plugins in configuration order.

Failure policy:

- Global-config read/parse failure is immediately fatal.
- Project-config read/parse failure is accumulated and becomes fatal after early setup.
- Pydantic validation failure is fatal.
- Record, strict-line-break, metamodel, marker, and plugin failures are fatal unless a documented warning path applies.

## 3. Main TOML model: `ConfigFile`

`ConfigFile` is the validated top-level project model. `input` is required. Other fields have defaults. The model does not explicitly set `extra='forbid'`; under the current Pydantic default, unknown top-level keys are ignored. `UNVERIFIED`: whether this permissive behavior is an intentional compatibility contract.

| Field | Type | Default | Runtime effect |
|---|---|---:|---|
| `base` | `str` | `..` | Base directory relative to config root; absolute values are accepted by `Path` semantics. |
| `language` | `str` | `en` | Report/change-report language; must be supported by i18n. |
| `log_level` | `str` | `info` | Console verbosity; normalized lowercase and validated against `debug`, `info`, `warning`, `error`, `silent`. |
| `warnings_as_errors` | `bool` | `false` | Promotes collected warnings to fatal completion failure. |
| `publish` | `PublishSectionConfig` | empty model | Global publish-config path and cross-input duplicate policy. Accepts legacy string form. |
| `output_path` | `str` | `outputs/` | Base for reports, changes, traces, and publish output; relative to config root. |
| `input` | `list[InputConfig]` | required | Ordered input source definitions. |
| `metrics` | `MetricsConfig` | default model | Metrics settings. |
| `impact` | `ImpactConfig` | default model | Impact and task-generation settings. |
| `metamodel` | `Metamodel` | default model | Optional `.syntagmax` DSL path. |
| `plugin` | `list[PluginConfig]` | `[]` | Ordered plugin definitions. |
| `drivers` | `DriversConfig` | default model | Global driver defaults. |
| `baseline` | `BaselineConfig` | default model | Baseline tag validation. |
| `trace` | `TraceConfig` | default model | Trace-export plugin names. |
| `ai` | `AiConfig` | default model | AI agent selection and prompt settings. |
| `report` | `ReportConfig` | default model | Error-path link rendering. |

### 3.1 Source/documentation discrepancy

- The reference table describes `base` as required.
- The Pydantic model supplies `base = ".."` when omitted.
- **Effective implementation rule:** omission uses `..` unless validation/config processing changes elsewhere; this discrepancy is `UNVERIFIED` as a documentation-intent question.

## 4. Input model: `[[input]]`

### 4.1 `InputConfig` fields

| Field | Type | Default | Validation/meaning |
|---|---|---:|---|
| `name` | `str` | required | Runtime record name; used for selection, report grouping, and output filename. |
| `dir` | `str` | required | Directory relative to resolved base directory. |
| `driver` | `str` | required | Extractor key, e.g. `obsidian`, `text`, `markdown`, `simple-markdown`, `ipynb`, `sidecar`. Driver existence is checked when extraction selects it. |
| `filter` | `str \| None` | `None` | Glob relative to record base; if absent, driver default may apply. |
| `atype` | `str` | `REQ` | Default artifact type for extracted artifacts. |
| `marker` | `str \| None` | `None` | Artifact marker; runtime falls back to `atype`. |
| `markers` | `list[str]` | `[]` | Obsidian fragment markers for non-artifact text blocks. |
| `publish` | `str \| None` | `None` | Per-record publish-config path, resolved relative to base directory. |
| `exclude_elements` | `list[ExcludeElementConfig] \| None` | `None` | Per-record Obsidian extraction exclusions; merged over global defaults. |
| `task_template` | `str \| None` | `None` | Per-record impact-task template, resolved relative to base directory. |

`InputConfig.exclude_elements` rejects duplicate element names within the same list.

### 4.2 Driver default globs

When `filter` is absent, `_read_input_records()` uses:

| Driver | Default glob |
|---|---|
| `obsidian` | `**/*.md` |
| `ipynb` | `**/*.ipynb` |
| `markdown` | `**/*.md` |
| `simple-markdown` | `**/*.md` |
| any other driver | `**/*` |

The resulting `InputRecord.filepaths` is materialized immediately with `Path(record_base).glob(glob)`.

- **Source behavior:** the inspected loader does not explicitly reject a missing record directory; it can produce an empty file list.
- **Documentation behavior:** reference docs describe pre-flight input-location validation.
- **Status:** the precise missing-directory contract is `UNVERIFIED`; do not infer a fatal error solely from the current `glob()` call.

### 4.3 Runtime `InputRecord`

The Pydantic input model is converted to a dataclass with:

| Runtime field | Derivation |
|---|---|
| `name` | `InputConfig.name` |
| `dir` | `InputConfig.dir` |
| `record_base` | `base_dir / dir` |
| `filepaths` | materialized glob results |
| `driver` | `InputConfig.driver` |
| `default_atype` | `InputConfig.atype` |
| `marker` | `InputConfig.marker or InputConfig.atype` |
| `filter_glob` | explicit filter, driver default, or `**/*` |
| `markers` | uppercased configured fragment markers |
| `publish_config` | `InputConfig.publish` |
| `exclude_elements` | merged/sorted exclusion definitions |
| `task_template` | `InputConfig.task_template` |

## 5. Fragment-marker rules

Markers are validated while runtime records are built:

1. They are allowed only for the `obsidian` driver.
2. Each marker must be nonempty.
3. Each marker must match `^[a-zA-Z0-9_-]+$`.
4. Duplicate markers are rejected case-insensitively.
5. A fragment marker cannot equal the artifact marker case-insensitively.
6. Valid markers are stored uppercase.
7. If a metamodel is loaded, each marker is also checked against attributes of the record’s default artifact type.
8. A marker/attribute collision is fatal.

`UNVERIFIED`: nested marker overlap/no-nesting behavior is enforced by the Obsidian extractor, not this configuration loader.

## 6. Exclusion configuration

### 6.1 `ExcludeElementConfig`

| Field | Type/default | Allowed values |
|---|---|---|
| `name` | required `str` | `callouts`, `headings`, `horizontal_rules`, `frontmatter`, `tags` |
| `mode` | `str`, default `string-on-start` | `only`, `string`, `string-on-start` |

Rules:

- Unknown names are rejected.
- Unknown modes are rejected.
- Duplicate names in one list are rejected.
- For Obsidian inputs, global `[drivers.obsidian].exclude_elements` is merged with record-level exclusions.
- Record-level definitions replace global definitions with the same name.
- Resolved exclusions are sorted by element name.
- Non-Obsidian inputs do not receive the global Obsidian exclusion list.

## 7. Driver configuration

### 7.1 `DriversConfig`

| Field      | Type/default                          | Effect                                                   |
| ---------- | ------------------------------------- | -------------------------------------------------------- |
| `obsidian` | `ObsidianDriverConfig`, default model | Global Obsidian extraction/publish integration defaults. |

### 7.2 `ObsidianDriverConfig`

| Field | Type/default | Effect |
|---|---|---|
| `exclude_elements` | list, `[]` | Global exclusion definitions merged into Obsidian records. |
| `integration` | bool, `false` | Enables reading Obsidian `.obsidian/app.json` settings. |
| `root` | `str \| None`, `None` | Override `.obsidian` directory, relative to base directory. |
| `strict_line_breaks` | `str \| bool`, normalized to string `on` | `on`/`true` = standard Markdown behavior; `off`/`false` = Obsidian relaxed hard-break transformation; `auto` = read `strictLineBreaks` from `app.json`. |

Coercion/validation:

- Boolean `true` becomes string `true`; Boolean `false` becomes string `false`.
- String values are lowercased and trimmed.
- Accepted values: `on`, `true`, `off`, `false`, `auto`.
- `auto` without `integration = true` is a fatal configuration error.
- Runtime resolution is cached by `Config.resolve_strict_line_breaks()`.
- Auto mode reads `<base>/<root or .obsidian>/app.json`.
- Missing/unreadable/malformed settings produce warnings and strict-mode fallback `True`.

## 8. Metrics configuration: `[metrics]`

`MetricsConfig` ignores unknown extra fields.

| Field | Type/default | Runtime consumer |
|---|---|---|
| `enabled` | bool, `false` | Enables metrics collection behavior. |
| `requirement_type` | str, `REQ` | Selects artifact type treated as a requirement and used for per-input metrics grouping. |
| `status_field` | str, `status` | Field used for status metrics. |
| `verify_field` | str, `verify` | Field used for verification metrics. |
| `tbd_marker` | str, `TBD` | Marker used to identify unresolved/TBD values. |

## 9. Impact configuration: `[impact]`

`ImpactConfig` ignores unknown extra fields.

| Field | Type/default | Runtime consumer |
|---|---|---|
| `enabled` | bool, `false` | Enables impact-analysis behavior. |
| `tasks_enabled` | bool, `false` | Enables impact-task generation after impact analysis. |
| `tasks_dir` | str, `tasks/` | Generated task directory, relative to config root. |
| `tasks_template` | `str \| None`, `None` | Global Jinja2 task template, relative to config root. |
| `task_atype_map` | `dict[str, str]`, `{}` | Maps `parent_atype/child_atype` to task artifact type; downstream fallback is `TASK`. |

Precedence:

```text
CLI --tasks → impact.tasks_enabled = true
config tasks_enabled → normal setting
```

Task-template resolution:

1. record `task_template`, relative to base directory;
2. global `impact.tasks_template`, relative to config root;
3. built-in `task.j2` package resource.

`Config.tasks_dir()` resolves `root_dir / impact.tasks_dir`; this is independent of `output_path`.

## 10. Report configuration: `[report]`

`ReportConfig` ignores unknown extra fields.

| Field | Type/default | Effect |
|---|---|---|
| `path_as_links` | bool, `false` | Render report file paths as Markdown/Obsidian links rather than plain text. |
| `wiki_links` | bool, `false` | Use `[[wiki-link]]` syntax when path links are enabled; otherwise standard Markdown links. |

`wiki_links` has no visible effect while `path_as_links` is false.

## 11. Publish section in main TOML: `[publish]`

### 11.1 `PublishSectionConfig`

| Field | Type/default | Effect |
|---|---|---|
| `config` | `str \| None`, `None` | Global publish YAML/TOML path, resolved relative to config root. |
| `cross_input_duplicates` | bool, `true` | When true, explicit text-block IDs must be unique across inputs; false scopes checking per input. |

Compatibility/coercion:

- `publish = "file.yaml"` is accepted and converted to `PublishSectionConfig(config="file.yaml")`.
- String booleans accept `true`, `1`, `yes`, `false`, `0`, `no`, case-insensitively.
- Other string boolean values are rejected.
- Unknown fields are ignored by this model.

### 11.2 Misplaced publish warning

When no global publish config exists, there is more than one input record, and exactly one record has a per-record `publish` path, config loading emits a warning suggesting moving the setting to the global `[publish]` section. This warning can become fatal under warnings-as-errors.

## 12. Separate publish-file model

Publish files may be YAML, YML, or TOML. `PublishConfig` accepts field aliases in both Python names and configured aliases where enabled.

### 12.1 `PublishConfig`

| Field | Type/default | Validation/effect |
|---|---|---|
| `start_level` | int, `1` | Heading-level offset. |
| `remove_numeric_prefixes_in_headers` | bool, `true` | Strip numeric heading prefixes. |
| `include_plain_text` | bool, `true` | Include unmarked text blocks. |
| `contents_marker` | str, `_contents_` | Filename marker for headingless content files; nonempty, no `/` or `\\`. |
| `table_spacer` / `table-spacer` | int, `1` | Table spacing; inclusive range `0..20`. |
| `attribute_presence` / `attribute-presence` | literal `all`, `mandatory`, `values-only`; `values-only` | Metadata visibility policy. |
| `render` | `dict[str, list[RenderSection]]`, `{}` | Per-type/marker render rules. |
| `docx_template` / `docx-template` | `DocxTemplate \| None`, `None` | DOCX template defaults and overrides. |

Unknown publish fields are not explicitly forbidden by `PublishConfig`; `TableSection` and all render section models are stricter where noted.

### 12.2 Render section models

#### `DocxTemplate`

| Field | Type/default | Rule |
|---|---|---|
| `default-template` / `default_template` | `str \| None`, `None` | Default DOCX reference document. |
| `overrides` | `dict[str, str]`, `{}` | Record-specific template paths. |

Extra fields are forbidden.

#### `AttributeRender`

| Field | Type/default | Rule |
|---|---|---|
| `alias` | required `str` | Display label for an attribute. |

#### `TableSection`

| Field | Type/default | Rule |
|---|---|---|
| `type` | literal `table` | Required discriminator. |
| `spacer` | int or null, `None` | Optional override, range `0..20`. |
| `attribute-presence` / `attribute_presence` | literal or null, `None` | Section-level presence override. |
| `attributes` | list of one-key dictionaries | Every dictionary must contain exactly one attribute key. |

Extra fields are forbidden.

#### `TextSection`

| Field | Type/default | Rule |
|---|---|---|
| `type` | literal `text` | Required discriminator. |
| `mode` | literal `block` or `inline` | Text placement mode. |
| `attributes` | list of one-key dictionaries | Every dictionary must contain exactly one attribute key. |

Extra fields are forbidden.

#### `MarkerRenderSection`

| Field | Type/default | Rule |
|---|---|---|
| `type` | literal `text` | Required discriminator. |
| `mode` | literal `block` or `inline` | Text placement mode. |
| `alias` | required `str` | Rendered marker label. |

Extra fields are forbidden.

### 12.3 Publish file loading and precedence

`Config.load_publish_config(record)` uses:

1. `record.publish_config`, resolved relative to base directory; explicit missing file is fatal;
2. global `publish.config`, resolved relative to config root; explicit missing file is fatal;
3. auto-discovery in config root: `publish.yaml`, `publish.yml`, then `publish.toml`;
4. built-in `PublishConfig()` defaults.

File rules:

- `.yaml`/`.yml` → `yaml.safe_load`.
- `.toml` → `tomllib.loads`.
- Other suffix → fatal unsupported-format error.
- Parse/model errors → fatal with source path.
- Auto-discovery rejects a YAML variant together with `publish.toml`.
- If both `publish.yaml` and `publish.yml` exist, the current resolver selects `publish.yaml`; `UNVERIFIED`: whether this should be a conflict error.

## 13. Plugin configuration: `[[plugin]]`

### 13.1 `PluginConfig`

| Field | Type/default | Validation/effect |
|---|---|---|
| `name` | required str | Plugin discovery name; cannot be `.`, `..`, or contain `/` or `\\`. |
| `source` | required literal `local` or `package` | Selects local-file or entry-point loading. |
| `enabled` | bool, `true` | Disabled plugins are skipped. |
| `params` | dict, `{}` | Plugin-specific parameters passed to hooks. |

Extra plugin fields are forbidden.

### 13.2 Loading rules

- Plugins load in TOML list order.
- Disabled plugins do not load or appear in the active runtime list.
- Local source searches `<config_root>/plugins/<name>.py`, then `<config_root>/plugins/<name>/__init__.py`.
- Package source searches entry-point group `syntagmax.plugins` by name.
- Missing/invalid/load-error plugins raise `FatalError`.
- Loaded plugin runtime state contains name, module, and params.
- Hook behavior is downstream, but configuration controls active order and parameters.

## 14. Trace configuration: `[trace]`

| Field | Type/default | Effect |
|---|---|---|
| `plugins` | `list[str]`, `[]` | Names of active plugins used by the `trace` command for sequential export. |

The names are resolved against enabled plugins. A configured name that is not loaded is fatal when trace export runs.

## 15. Baseline configuration: `[baseline]`

| Field | Type/default | Effect |
|---|---|---|
| `tag_pattern` | `str \| None`, `None` | Optional regular expression used with full matching for baseline tag names. |

The regex is compiled during Pydantic validation; invalid syntax is a configuration error. No pattern means any tag name is accepted by the model.

## 16. AI configuration: `[ai]`

`AiConfig` ignores unknown extra fields.

| Field | Type/default | Effect |
|---|---|---|
| `agent` | str, `kiro` | Default CLI agent name for `ai verify`. |
| `persona` | str, `You are a systems engineer reviewing requirements traceability.` | Persona injected into verification prompts. |
| `agents_file` | `str \| None`, `None` | Custom agent registry YAML path, relative to config root. |

## 17. Metamodel configuration: `[metamodel]`

| Field | Type/default | Effect |
|---|---|---|
| `filename` | str with default `None` | `.syntagmax` DSL path relative to config root. |

- If set, `load_metamodel()` parses and validates it; errors are fatal.
- If omitted, config loading logs `No static validation model` and sets `Config.metamodel = None`.
- Marker/attribute collision validation is skipped when no model is loaded.

## 18. Path resolution API

`Config` exposes these derived values:

| Method/property | Rule |
|---|---|
| `root_dir()` | Absolute parent directory of selected config file. |
| `base_dir()` | `Path(root_dir, base)`; source repository/vault root. |
| `output_dir()` | Absolute `output_path` as-is; otherwise `root_dir / output_path`. |
| `tasks_dir()` | `root_dir / impact.tasks_dir`; independent of output path. |
| `derive_path(path)` | Absolute path relative to absolute base directory, returned POSIX-style. |
| `input_records()` | Materialized runtime input records in config order. |
| `plugins()` | Enabled loaded plugins in config order. |
| `trace_plugins` | `trace.plugins`. |
| `obsidian_driver_config` | Global Obsidian model. |
| `baseline_config` | Baseline model. |
| `ai_config` | Alias for `Config.ai`. |
| `cross_input_duplicates` | Main publish duplicate policy. |

Relative-path bases:

- `base`: config root.
- input `dir`: base directory.
- input `publish`: base directory.
- global `publish.config`: config root.
- `output_path`: config root.
- `impact.tasks_dir`: config root.
- `impact.tasks_template`: config root.
- input `task_template`: base directory.
- Obsidian `root`: base directory.
- AI `agents_file`: config root.
- metamodel `filename`: config root.

## 19. Runtime precedence summary

```text
CLI explicit values
  > project TOML
    > global TOML
      > Pydantic/model defaults
```

Important exceptions:

- Per-record publish file > global publish file > auto-discovery > built-in publish defaults.
- Per-record task template > global task template > built-in task template.
- Per-record Obsidian exclusion with the same name > global driver exclusion.
- `--tasks` forces `impact.tasks_enabled = true`; there is no corresponding CLI force-off in the inspected loader.
- `--log`, `--warnings-as-errors`, and `--lang` are CLI-over-config overrides.

## 20. Configuration invariants and risks

- `input` is the only required top-level model field; operationally useful projects usually also need a valid metamodel and existing input directories.
- `contents`/`id` metamodel requirements are validated by the metamodel loader, not by `ConfigFile`.
- Config loading can emit warnings before full model validation; warnings-as-errors can turn them into fatal completion errors.
- Input file lists are captured at config construction time; later filesystem changes are not automatically reflected in the same `Config` instance.
- Per-record and global path bases differ intentionally; moving config files can change behavior without changing TOML strings.
- Publish and task templates have independent resolution chains.
- Plugin loading happens after most config validations; a plugin load failure prevents a usable runtime `Config`.
- The generated init `.gitignore` contains `reports/`, while current default output is `outputs/`; this source-level naming mismatch is `UNVERIFIED` as intentional legacy behavior.

## 21. Evidence status

- **Confirmed by source:** model fields/defaults, validators, global/project merge order, CLI precedence hooks, path methods, input-record materialization, publish/task precedence, marker/exclusion validation, plugin loading, and metamodel/language setup.
- **Confirmed by focused tests/docs:** config existence guard, config base-path resolution, log/warnings precedence, strict-line-break values, baseline model validation, publishing configuration behavior, and generated init settings.
- **`UNVERIFIED`:** exact unknown-field compatibility policy, missing input-directory fatality, both-YAML auto-discovery conflict policy, all path edge cases involving symlinks/relative `..`, and every downstream consumer’s response to omitted optional sections.
