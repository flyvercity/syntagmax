---
type: Operations Guide
title: Operations Guide
description: Guide on using the Syntagmax repository from the command line, including CLI commands and workflows.
tags: [operations, cli, guide]
---

# Operations Guide

This page focuses on how the repository is used from the command line and what to watch out for when running it in practice.

## CLI entrypoints
The package exposes a `syntagmax` console script via `pyproject.toml`.

Main commands in `src/syntagmax/cli.py`:
- `init` — create a `.syntagmax` project scaffold
- `analyze` — run the analysis pipeline and write a report
- `publish` — render records to Markdown, optionally DOCX/PDF
- `edit renumber` — renumber artifact IDs
- `mcp run` — start the MCP server
- `ci` — configure GitHub and GitLab pipelines
- `change baseline` — create baseline tags across repositories
- `edit attrs` — bulk attribute manipulation
- `markers renumber` — renumber fragment markers
- `schema` — generate JSON schemas for configurations

## Typical workflows
### Initialize a project
`uv run syntagmax init`

This creates the `.syntagmax` workspace files needed by later commands.

### Run analysis
`uv run syntagmax analyze`

Key options:
- `--config-file` chooses the project TOML
- `--cwd` changes working directory before execution
- `--no-git` skips revision extraction
- `--render-tree` appends a textual tree view to the report
- `--output console` prints markdown to stdout instead of writing a file
- `--locale` sets the locale for localized change reports (e.g., `--locale ru`)

The command defaults to writing `.syntagmax/reports/report.md`.

### Generate change reports
`uv run syntagmax analyze --change-report`
`uv run syntagmax analyze --change-report --summary`

Change reports now support:
- Grouping changes by file.
- Summary mode for concise overviews.
- Localization via the `--locale` flag.
- Binary artifact change reporting via sidecar metadata.

### Publish records
`uv run syntagmax publish RECORD_A RECORD_B`
`uv run syntagmax publish --all`
`uv run syntagmax publish --all --single`

Important behaviors:
- `--all` and explicit record names are mutually exclusive in practice, but one of them must be provided.
- `--single` writes a consolidated Markdown file; without it, each record gets its own file.
- `--date-suffix` only applies to separate output files.
- `--docx` and `--pdf` are graceful add-ons: if Pandoc is missing, Markdown still gets written and the command does not fail.
- Plugins run during publish: pre-publishing filters can mutate the block tree, and post-processing plugins can transform the Markdown.
- Images referenced in source documents are automatically resolved and copied to the output directory.
- `--attribute-presence` enables filtering artifacts based on attribute conditions.
- **Configurable table spacing** improves readability in published output.

### Start the MCP server
`uv run syntagmax mcp run .syntagmax/config.toml --transport sse --port 8000`

The server loads and analyzes artifacts first, then serves tools for listing, searching, and reading content.

## Working with config files
`config.py` looks for a project config file and can merge a global config from `~/.config/syntagmax/config.toml`. That global config is real runtime behavior and matters when reproducing user environments.

The code supports per-input publish TOML or YAML files. If a record references one, it takes precedence over default publish paths (`.syntagmax/publish.toml` or `.syntagmax/publish.yaml`).

## Operational caveats
- Missing config files are a hard error in the CLI.
- Publish output paths differ between single-file and per-record mode, so check the branch you are on before editing docs or tests.
- Plugin errors halt publishing and are surfaced as `FatalError`.
- Metamodel validation is strict; invalid DSL definitions fail early.
- Git history extraction can be skipped, but many analysis and MCP behaviors assume revisions are available.
- **Pre-flight validation** for input record locations ensures all input files exist before processing.
- **Redacted logging** in AI providers ensures sensitive headers, bodies, and URLs are not exposed in logs.
- **Localization** is supported in change reports for file status strings and other user-facing messages.
- **Summary mode** for change reports provides a high-level overview of changes, complementing detailed reports.
- Change reports now support localization, but ensure the requested locale is available in `src/syntagmax/resources/locales/`.
- Binary artifact change reporting requires sidecar metadata to be properly configured.

## Example assets
The `example/` directory contains runnable samples that exercise the main workflows:
- `example/obsidian-driver/` for extraction and analysis
- `example/publishing/` for publish formatting
- `example/plugin-demo/` for plugin behavior
- `example/error-handling/` and `example/renumber-demo/` for edge cases

Those examples are the best place to inspect the expected end-to-end shape of input config, source files, and output artifacts.
 inspect the expected end-to-end shape of input config, source files, and output artifacts.
