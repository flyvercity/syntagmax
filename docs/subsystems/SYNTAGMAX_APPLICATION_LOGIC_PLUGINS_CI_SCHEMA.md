# Syntagmax Application Logic — Plugins, CI, and Schema Subsystem

> Covers plugin configuration/loading/hooks plus JSON-schema and CI workflow generation. Source: `plugin.py`, `cli_tools.py`, `config.py`, and focused tests.

## 1. Plugin model

`PluginConfig` fields:

| Field | Default/rule |
|---|---|
| `name` | required; no `.`, `..`, `/`, or `\\` |
| `source` | required literal `local` or `package` |
| `enabled` | `true` |
| `params` | `{}` |

Enabled plugins load in configuration order into `LoadedPlugin(name, module, params)`. Disabled plugins are skipped.

## 2. Plugin discovery

### Local

Search under config root:

1. `plugins/<name>.py`;
2. `plugins/<name>/__init__.py`.

The module is loaded under a clean `syntagmax.plugins.local.<name>` namespace.

### Package

- Query entry-point group `syntagmax.plugins` by exact name.
- No entry point, query failure, load failure, or non-module target is fatal.
- A callable entry point may be converted to its owning module only when its module is available.

Any enabled plugin load failure prevents a usable `Config`.

## 3. Hooks

### `transform_blocks(tree, config, params)`

- Runs in configured order.
- Must return `BlockTree`.
- Exception or wrong return type → `FatalError`.

### `filter_block(block, file_record, config, params)`

- Named pre-filter only.
- Runs once per block.
- May return a replacement `Block` or `None` to omit it.
- Missing hook, exception, or wrong return type → `FatalError`.

### `transform_markdown(markdown, config, params)`

- Runs in configured order after rendering.
- Must return `str`.
- Exception or wrong return type → `FatalError`.

### `export_trace(matrix, config, params)`

- Used by configured trace plugins.
- Missing hook or exception → `FatalError`.
- All configured trace plugins receive the same matrix sequentially.

### Plugin lookup

`find_plugin_by_name()` searches enabled loaded plugins only. Failure reports available names or that no plugins are configured.

## 4. CI generation

`ci --target` accepts `github` (default) or `gitlab`; nested install commands write files in the current working directory after root `--cwd` handling.

### Analyze workflow

- GitHub: `.github/workflows/syntagmax-analyze.yml`.
- GitLab: `.gitlab-ci.yml`.
- Installs Syntagmax through `uv`.
- Runs `syntagmax analyze`.
- Publishes `.syntagmax/outputs/report.md`.
- GitHub uses manual dispatch, checkout, setup-uv, and read-only contents permission.
- GitLab uses a web-pipeline rule and Python 3.13 image.

### Publish workflow

- GitHub: `.github/workflows/syntagmax-publish.yml`.
- GitLab: `.gitlab-ci.yml`.
- Runs `syntagmax publish --all --single`.
- Publishes `.syntagmax/outputs/publish/published.md`.

Existing workflow files are overwritten by `write_text()`; no confirmation is implemented. `UNVERIFIED`: exact generated YAML validity across all runner versions.

## 5. JSON schema generation

- `schema publish` prints `PublishConfig.model_json_schema()` as indented JSON.
- `schema config` prints `ConfigFile.model_json_schema()` as indented JSON.
- These commands do not load a project config or plugins.
- Schema shape reflects Pydantic aliases/constraints and may omit runtime path/precedence behavior.

## 6. Extension invariants

- Plugin order is configuration order, not discovery order.
- Disabled plugin names remain in config but are unavailable to named runtime lookup.
- Hooks are intentionally type-checked at runtime.
- CI/schema generation writes local files and does not commit or push them.
- **`UNVERIFIED`:** plugin package entry-point behavior under multiple same-name distributions and generated schema ordering.
