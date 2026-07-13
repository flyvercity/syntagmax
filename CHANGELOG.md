# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Calendar Versioning](https://calver.org/) with the scheme `YYYY.M.D`.

## [2026.7.13] - 2026-07-13

### Added

- Attribute presence mode for publishing (show/hide attributes based on presence)
- Image reference rewriting in artifact rendering
- Configurable table spacing for published output
- `edit markers renumber` command for sequential marker ID assignment
- `strict_line_breaks` configuration for Obsidian driver (off/auto modes)
- Global publish configuration support
- Configurable removal modes for Obsidian element exclusion
- Identified text blocks (block ID generation in markdown extractor)
- TOML-based publishing configuration
- Content files support for headingless rendering
- Obsidian attachment folder integration (reads `.obsidian/app.json`)
- Hierarchical heading depth for document content
- Pre-publishing filter plugin hook (`filter_block`)
- Automatic image resolution and copying for published documents
- Configurable DOCX templates for Pandoc export
- Hierarchical path-based headings for published documents
- Regression tests for forward trace type filtering

### Fixed

- Remove automatic alt text generation for images
- Handle missing text fields in markdown extraction
- Preserve line endings and handle unclosed fences
- Detect and report conflicting nominal revisions in parent links
- Bound terminator search to next marker in markdown parser
- Constrain YAML search when `[/MARKER]` terminator is absent
- Deduplicate ParentLinks in `populate_pids`
- Propagate ancestors transitively in `gather_ancestors`
- Filter wrong-type parents from trace matrix
- Constrain YAML block search to segment boundaries
- Prevent Gemini API key exposure in logs and URLs
- Resolve TBD detection failure for list-valued fields
- Use ruamel.yaml for robust artifact attribute updates
- Resolve line update ordering in edit operations

### Changed

- Improved fragment marker parsing and validation
- Improved blank line consumption logic
- Improved Pandoc template resolution for individual record exports
- Moved block ID generation to markdown extractor
- Removed dead helper functions and imports in render module

## [2026.7.6] - 2026-07-06

Initial public release.

### Added

- Core analysis pipeline with DAG-based execution (extract → tree → impact → metrics)
- Obsidian, Markdown, Text, and Sidecar artifact extractors
- Metamodel DSL with attribute types: string, integer, boolean (with custom values), enum, and reference
- Support for multiple attributes, comma-separated enums, and multi-value parent references
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
- Localisation support via Babel
- Project metrics: requirement coverage, TBD detection, status tracking
