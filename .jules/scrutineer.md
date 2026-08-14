# Scrutineer's Journal

## Architectural Traps & Insights

### 1. Test-Only Internal Entry Points (Cargo-Cult Testing)
- **Insight:** In `src/syntagmax/extractors/markdown.py`, `_extract_from_markdown` is obsolete dead code in the actual runtime codebase, but it was kept alive solely because unit tests in `tests/test_hyphen_support.py` call it directly.
- **Rule of Thumb:** Avoid exposing or keeping internal-only helper entry points purely for tests. Tests should exercise the public, configured pipeline to ensure internal refactoring doesn't break tests unnecessarily and to prevent dead-code accumulation.

### 2. Dead Rebuilding Helpers in Extractors
- **Insight:** Extractors in Syntagmax are responsible for parsing/reading, but writing and round-tripping are delegated to `update_artifacts` or `edit.py`. The `_rebuild_file` method in `SimpleMarkdownExtractor` was an obsolete, non-roundtrip-safe duplicate of `_serialize_frontmatter`.
- **Rule of Thumb:** Keep extractors single-purpose. If editing is needed, keep serializer methods clearly separated, minimal, and fully used, while purging obsolete drafts.

### 3. Redundant "Just-In-Case" Singular Update Methods
- **Insight:** Over-engineering often leads to duplicating singular update methods (`update_artifact`) along with bulk update methods (`update_artifacts`). Keeping both when only one is called adds dead code and raises maintenance overhead.
- **Rule of Thumb:** Always favor batch/bulk interfaces (`update_artifacts`) and completely purge obsolete single-item wrappers once the system transitions to bulk operations.
