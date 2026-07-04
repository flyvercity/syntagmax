# Domain Model and File Formats

This repository is centered on artifacts, traces, and renderable blocks. The same conceptual data appears in different stages: parsed artifacts, analysis trees, publish blocks, and final published documents.

## Core domain objects
- `Artifact` in `src/syntagmax/artifact.py` is the basic unit of extracted content.
- `BlockTree`, `InputBlock`, `FileRecord`, `TextBlock`, `ArtifactBlock`, and `ErrorBlock` in `src/syntagmax/blocks.py` represent the publish-side hierarchy.
- `InputRecord` in `src/syntagmax/config.py` describes a configured source of files to process.
- `PublishConfig` in `src/syntagmax/publish_config.py` describes how artifacts and text blocks should be rendered.

## Artifact identity and structure
Artifacts are keyed by artifact ID and have an artifact type (`atype`). The pipeline assumes certain fields exist or can be derived:
- `id`
- `contents`
- optional metadata fields such as `parent`, `status`, `verify`, tags, and other metamodel-defined attributes

The metamodel loader validates that artifacts define an ID rule and a contents rule, and that conditional rules only depend on a non-conditional boolean anchor.

## Input sources and drivers
`config.py` supports input records with a `driver` field and a file filter. The codebase already includes drivers for:
- `obsidian` Markdown-style sources
- `markdown`
- `ipynb`
- `text`
- sidecar-style metadata handling in the extractor layer

Driver defaults matter because they affect what files are even discovered. For example, the config layer supplies default glob filters for some drivers.

## Publish block model
Publishing operates on a nested block structure rather than directly on artifacts. This lets the renderer preserve plain text around artifact records and treat marked fragments separately.

A publish pass usually works like this:
1. Extract files into blocks.
2. Group blocks under input records and files.
3. Render artifacts and text blocks according to publish config.
4. Apply plugin transforms if configured.
5. Emit Markdown or convert it to other formats.

## Publish configuration semantics
`PublishConfig` controls how the renderer behaves:
- `start_level` offsets heading depth
- `remove_numeric_prefixes_in_headers` strips section numbering from headings
- `include_plain_text` toggles unmarked text blocks
- `ignore_plain_text_prefixes` filters out lines with certain prefixes
- `render` maps artifact types or markers to ordered sections

The key behavior is fallback rendering. If a type or marker has no explicit render rule, the publisher emits a heading, contents, and a metadata table.

## Metamodel DSL
`src/syntagmax/metamodel.py` parses the project’s `.syntagmax` DSL with Lark. The DSL supports artifact definitions and trace rules. The loader validates the metamodel immediately and raises `FatalError` if the model is inconsistent.

Because the metamodel drives extraction and validation, changes here usually require updates to both fixtures and tests.

## Git-derived domain data
Artifacts can carry revision information extracted from Git. That supports impact analysis and traceability. The MCP server also exposes this graph data so clients can inspect a requirement together with its parents, children, and latest revision.

## Source references
- Artifacts: `src/syntagmax/artifact.py`
- Blocks: `src/syntagmax/blocks.py`
- Config: `src/syntagmax/config.py`
- Publish config: `src/syntagmax/publish_config.py`
- Metamodel: `src/syntagmax/metamodel.py`
- Extractors: `src/syntagmax/extractors/`
- Publish renderer: `src/syntagmax/publish.py`
- Git integration: `src/syntagmax/git_utils.py`
- MCP server: `src/syntagmax/mcp/server.py`
