# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Calendar Versioning](https://calver.org/) with the scheme `YYYY.M.D`.

## [2026.7.17] - 2026-07-17

### Added

- Change report command (`change report`) with support for comparing artifacts between Git revisions
- Summary mode for change reports (`--summary` flag)
- Sidecar-managed binary artifact change reporting (images, diagrams)
- Pre-flight validation for input record locations
- Localisation for change reports

### Fixed

- Localise file status strings in change rendering
- Escape artifact IDs and table values to prevent markdown injection
- Prevent HTML interpretation of angle brackets in change reports
- Make sidecar YAML key lookup case-insensitive
- Ensure sidecar extractor values are strings
- Resolve empty changed files section in change report
- Correct line number estimation in change reports
- Replace incorrect `lstrip`/`rstrip` with `removeprefix`/`removesuffix`
- Implement `--no-git` flag logic
- Fix potential trailing markdown backticks in model responses
- Simplify mandatory attribute logic by ignoring conditions
- Allow `id` attribute in mandatory attribute list
- Resolve missing images in multi-record DOCX publication
- Ensure robust pandoc subprocess execution on Windows
- Redact OpenAI header debug output and harden header logging

### Security

- Redact sensitive headers, bodies, URLs, and failure responses in AI provider logs
- Fix unredacted Gemini API request body logging

### Changed

- Restructure change report to group changes by file
- Update content comparison to use artifact fields
- Make worktree gitignore check path-agnostic
- Format undefined artifact IDs with backticks in reports

### Performance

- Precompute and cache truthy sets in `evaluate_condition`
- Optimise `get_artifact_field_value` case-insensitive lookups via lazy caching
- Optimise case-insensitive field exclusion in `render_artifact_fallback`
- Cache regex compilation and optimise string concatenation

### Refactored

- Reduce cyclomatic complexity in markdown extraction, BedrockProvider, and `_validate_attributes`
- Add PEP 257 docstrings to AI provider modules
- Clean up unused imports and dead code in change report generation
- Log a warning when `git_utils.is_dirty` catches Git exceptions

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
