# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-07-06

Initial public release.

### Added

- Core analysis pipeline with DAG-based execution (extract → tree → impact → metrics → AI)
- Obsidian, Markdown, Text, Sidecar, and Jupyter Notebook artifact extractors
- Metamodel DSL with attribute types: string, integer, boolean (with custom values), enum, and reference
- Support for multiple attributes, comma-separated enums, and multi-value parent references
- Hyphens and underscores in attribute identifiers
- Custom `atype`/`marker` decoupling for input sources
- Marked text fragments (Obsidian driver): `[COM]`, `[NOTE]`, etc.
- Git revision extraction via `git blame` for artifact change history
- Impact analysis: via-commit (revision pinning) and via-timestamp modes
- Traceability matrix export (CSV/TSV) with forward/reverse, flat mode, left outer join, and plugin hook
- Publishing pipeline: block-tree rendering to Markdown with Pandoc DOCX/PDF conversion
- Publishing configuration: per-record output, `--single` consolidated mode, `--date-suffix`
- Plugin system: local file and package entry-point plugins with `transform_blocks`, `transform_markdown`, and `export_trace` hooks
- Bulk attribute manipulation (`edit attrs`): add/del/replace with CSV import support
- Artifact renumbering (`edit renumber`) with configurable ID schemas
- Unified Markdown report output (errors, tree, metrics, impact, AI analysis)
- MCP server with `list_artifacts`, `search_artifacts`, and `get_artifact_content` tools
- `syntagmax init` command for project scaffolding
- Configurable AI providers: Ollama, Anthropic, OpenAI, Gemini, AWS Bedrock
- Localisation support (English, Russian) via Babel
- Project metrics: requirement coverage, TBD detection, status tracking
