# Scrutineer's Journal

## Architectural Traps & Insights

### 1. Test-Only Internal Entry Points (Cargo-Cult Testing)
- **Insight:** In `src/syntagmax/extractors/markdown.py`, `_extract_from_markdown` is obsolete dead code in the actual runtime codebase, but it was kept alive solely because unit tests in `tests/test_hyphen_support.py` call it directly.
- **Rule of Thumb:** Avoid exposing or keeping internal-only helper entry points purely for tests. Tests should exercise the public, configured pipeline to ensure internal refactoring doesn't break tests unnecessarily and to prevent dead-code accumulation.

### 2. Dead Rebuilding Helpers in Extractors
- **Insight:** Extractors in Syntagmax are responsible for parsing/reading, but writing and round-tripping are delegated to `update_artifacts` or `edit.py`. The `_rebuild_file` method in `SimpleMarkdownExtractor` was an obsolete, non-roundtrip-safe duplicate of `_serialize_frontmatter`.
- **Rule of Thumb:** Keep extractors single-purpose. If editing is needed, keep serializer methods clearly separated, minimal, and fully used, while purging obsolete drafts.
