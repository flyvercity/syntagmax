# OpenWiki Quickstart

Syntagmax is a git-friendly requirements management system for extracting artifacts from source documents, building a traceable artifact tree, analyzing changes and impact, and publishing rendered documentation. The codebase also includes an MCP server so LLM clients can inspect requirements directly.

## Start here
- [Architecture overview](architecture.md)
- [Domain model and file formats](domain.md)
- [Operations guide](operations.md)
- [Testing guide](testing.md)

## What this repository does
- Discovers input records from a TOML project config and processes them through a dependency-ordered analysis pipeline.
- Extracts artifacts from multiple drivers, including Obsidian-style Markdown, plain Markdown, text markers, sidecar metadata, and IPython notebooks.
- Builds a tree of artifacts, validates the metamodel, computes metrics, performs impact analysis, and optionally runs AI-assisted analysis.
- Publishes artifact collections to Markdown, and can optionally convert output to DOCX or PDF via Pandoc.
- Supports local and package plugins that transform the publish pipeline.
- Exposes a small MCP server with tools for listing, searching, and retrieving artifact content.

## High-signal source map
- CLI entrypoint: `src/syntagmax/cli.py`
- Pipeline orchestration: `src/syntagmax/main.py`
- Configuration loading: `src/syntagmax/config.py`
- Metamodel DSL: `src/syntagmax/metamodel.py`
- Extraction layer: `src/syntagmax/extract.py` and `src/syntagmax/extractors/`
- Tree / analysis logic: `src/syntagmax/tree.py`, `src/syntagmax/analyse.py`, `src/syntagmax/impact.py`, `src/syntagmax/metrics.py`, `src/syntagmax/ai.py`
- Publish pipeline: `src/syntagmax/publish.py`, `src/syntagmax/publish_config.py`, `src/syntagmax/pandoc.py`
- Plugin system: `src/syntagmax/plugin.py`
- MCP server: `src/syntagmax/mcp/server.py`
- Representative tests: `tests/test_init.py`, `tests/test_publish.py`, `tests/test_plugin.py`, `tests/test_mcp.py`, `tests/test_metamodel.py`

## Project layout
- `src/syntagmax/` contains the runtime package.
- `tests/` contains unit and integration tests for config parsing, extraction, publishing, metamodel validation, plugins, and MCP behavior.
- `example/` contains sample repositories used by the README and tests as end-to-end fixtures.
- `docs/` contains the project’s prior design/specification material; OpenWiki links to the parts that are still useful as implementation evidence.

## Common change paths
- Changing how artifacts are discovered or parsed: start in `src/syntagmax/extract.py`, then inspect the relevant driver in `src/syntagmax/extractors/` and the matching tests.
- Changing validation or the DSL: start in `src/syntagmax/metamodel.py` and `tests/test_metamodel*.py`.
- Changing publish output: start in `src/syntagmax/publish.py`, `src/syntagmax/publish_config.py`, and `tests/test_publish.py`.
- Changing plugins: start in `src/syntagmax/plugin.py` and `tests/test_plugin.py`.
- Changing CLI workflows: start in `src/syntagmax/cli.py` and `tests/test_init.py`, `tests/test_publish.py`, `tests/test_mcp.py`.

## Before you edit
- Confirm the input record shape in `src/syntagmax/config.py` before changing any pipeline assumptions.
- Check `README.md` and the relevant `docs/specs/*.md` files for behavior that is already documented or intentionally constrained.
- For publish changes, watch the defaults for output paths, `--single` behavior, and whether Pandoc should fail open or fail closed.
- For plugin changes, preserve load order and the runtime validation of hook return types.

## Recent architecture changes to know about
Recent commits added the configurable publish system, Pandoc export, and the plugin pipeline. Those changes mean the publish path is no longer a single hardcoded renderer; it now layers config-driven rendering, optional plugins, and optional format conversion.

Related evidence:
- `e2c4146 feat: implement configurable publishing system`
- `d835f71 feat: add pandoc integration for docx and pdf export`
- `a180058 feat: implement plugin system for transformation pipeline`

## Useful docs already in the repo
- `README.md` remains the user-facing introduction.
- `docs/internal.md` is a useful internal process overview.
- `docs/specs/publish-config.spec.md`, `docs/specs/publishing-word.md`, and `docs/specs/plugin-system.md` are the highest-signal design docs for current publish behavior.
