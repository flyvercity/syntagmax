# Architecture Overview

Syntagmax is organized around a dependency-driven analysis pipeline with a separate publish pipeline and a small MCP server. The runtime package lives under `src/syntagmax/` and the CLI is the primary entrypoint.

## Runtime shape
- `src/syntagmax/cli.py` defines the Click command group and the `init`, `analyze`, `publish`, `edit`, and `mcp` command surfaces.
- `src/syntagmax/main.py` defines the analysis DAG, resolves dependencies for requested steps, and executes them in order.
- `src/syntagmax/config.py` loads TOML configuration, merges global and project config, validates the input records, and loads the metamodel, plugins, and localization settings.
- `src/syntagmax/report.py` renders the combined analysis report through a Jinja2 template, now with localization support via `babel`.
- `src/syntagmax/i18n.py` provides localization utilities for change reports and other user-facing messages.

## Analysis pipeline
The analysis path is dependency-ordered rather than hardcoded. `main.py` defines the step graph:
- `extract`
- `build_artifact_map`
- `populate_pids`
- `build_tree`
- `tree`
- `populate_revisions`
- `impact`
- `metrics`
- `ai`

The CLI’s `analyze` command lets the user request a public step target; `main.process()` computes the necessary dependency closure and runs just those steps.

Important consequence: if you change one step, check whether downstream steps assume the same intermediate shapes (`artifacts_list`, `artifacts`, tree nodes, or revision metadata).

## Publish pipeline
The publish path is distinct from analysis and now includes image resolution, pre-publishing filter plugins, and configurable rendering options.

1. `cli.py publish` loads the project config and selects one or more input records.
2. `publish.build_block_tree()` extracts blocks per record and preserves file order, now with support for ATX heading splitting in Markdown sources.
3. `publish.resolve_images()` resolves and copies images referenced in source documents to the output directory.
   - If Obsidian integration is enabled (`[drivers.obsidian] integration = true`), `RenderContext` lazily reads `.obsidian/app.json` to discover `attachmentFolderPath`. Image resolution checks this folder first (O(1)) before falling back to a vault-wide file scan.
   - Note-relative attachment paths (`./...`) are resolved per source file.
4. `plugin.run_block_transforms()` runs pre-publishing filter plugins that can mutate the block tree.
5. `publish.render_block_tree()` renders the block tree into Markdown using `PublishConfig`, now with support for:
   - **ATX heading splitting** in markdown extraction.
   - **Attribute presence mode** for filtering artifacts based on attribute conditions.
   - **Configurable table spacing** for improved readability.
   - **Image reference rewriting** to ensure published documents point to the correct image paths.
   - **Case-insensitive field exclusions** for artifact rendering.
6. `plugin.run_markdown_transforms()` runs post-processing plugins that can transform the Markdown.
7. The CLI writes `.md`, then optionally converts to `.docx` / `.pdf` via `pandoc.py`.

The publishing system is config-driven and record-specific. Each input record may point to its own publish YAML, with fallbacks to `.syntagmax/publish.yaml` or defaults.

## Configuration and metamodel layer
`config.py` is one of the highest-risk files in the repo because it combines several concerns:
- project TOML parsing
- global config merge from `~/.config/syntagmax/config.toml`
- input-record discovery and validation, including **pre-flight validation for input record locations**
- TOML-based publishing configuration support
- metamodel loading
- plugin loading

The metamodel loader in `metamodel.py` uses a Lark grammar to parse the `.syntagmax` DSL and validate constraints such as required `id` and `contents` rules, boolean anchors, and trace rule sanity. Recent optimizations include **simplified mandatory attribute logic** and **performance improvements** in validation.

## Plugin system
`plugin.py` implements a two-hook plugin model:
- `transform_blocks(tree, config, params) -> BlockTree` (pre-publishing filter)
- `transform_markdown(markdown, config, params) -> str` (post-processing)

Plugins may be local files/packages under the project’s `plugins/` directory or installed packages exposed through the `syntagmax.plugins` entry-point group. Hooks are run in config order and incorrect return types raise `FatalError`.

This means publish changes must be careful about plugin compatibility. The plugin API is intentionally small and should stay stable unless the repo’s extension model is changing on purpose.

## MCP server
`mcp/server.py` bootstraps a `FastMCP` server and exposes tools to:
- list artifacts
- search artifacts
- get artifact content with traceability metadata

The server initializes by extracting, mapping, assigning PIDs, building the tree, and running analysis so the tools can answer queries against a populated artifact graph.

## Source references
- CLI: `src/syntagmax/cli.py`
- Pipeline: `src/syntagmax/main.py`
- Config: `src/syntagmax/config.py`
- Metamodel: `src/syntagmax/metamodel.py`
- Publish renderer: `src/syntagmax/publish.py`
- Publish config: `src/syntagmax/publish_config.py`
- Plugins: `src/syntagmax/plugin.py`
- MCP: `src/syntagmax/mcp/server.py`
- Change rendering: `src/syntagmax/change_render.py`
- Markdown extraction: `src/syntagmax/extractors/markdown.py`
- AI providers: `src/syntagmax/ai_providers.py`
- Artifact handling: `src/syntagmax/artifact.py`
- Binary change reporting: `src/syntagmax/change_binary.py`
- Sidecar extraction: `src/syntagmax/extractors/sidecar.py`
- Localization: `src/syntagmax/i18n.py`
- Change rendering: `src/syntagmax/change_render.py`
- Markdown extraction: `src/syntagmax/extractors/markdown.py`
