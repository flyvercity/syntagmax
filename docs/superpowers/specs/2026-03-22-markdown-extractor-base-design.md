# Markdown Extractor Base Refactoring Spec

**Date:** 2026-03-22
**Status:** Approved
**Goal:** Introduce a common `MarkdownExtractor` base class to decouple `IPynbExtractor` from `ObsidianExtractor` and provide a foundation for future markdown-based drivers.

## Context
Currently, `IPynbExtractor` inherits from `ObsidianExtractor` to reuse its `[REQ]` parsing logic. This is architecturally incorrect as `IPynbExtractor` should not depend on a specific file driver's implementation. Furthermore, adding notebook-specific location logic to `ObsidianExtractor` "leaked" notebook concepts into a generic file driver.

## Proposed Architecture

### 1. `MarkdownExtractor` (Base Class)
- **File**: `src/syntagmax/extractors/markdown.py`
- **Responsibility**: Provides the core logic for identifying and parsing `[REQ]` blocks within markdown text.
- **Key Components**:
    - `MarkdownArtifact(Artifact)`: Generic artifact type for markdown sources.
    - `MarkdownTransformer(Transformer)`: Lark transformer for the `[REQ]` grammar.
    - `MarkdownExtractor(Extractor)`: 
        - Initializes the Lark parser using `markdown.lark`.
        - Implements `_extract_from_markdown(filepath: Path, markdown: str, location_builder: Callable[[int, int], Location])`.
- **Location Decoupling**: Uses a `location_builder` callback to allow subclasses to determine the exact `Location` type (e.g., `LineLocation` vs `NotebookLocation`).

### 2. `ObsidianExtractor` (Subclass)
- **File**: `src/syntagmax/extractors/obsidian.py`
- **Inheritance**: `MarkdownExtractor`
- **Responsibility**: Handles `.md` files in Obsidian vaults.
- **Future-proofing**: Will host Obsidian-specific features like Wikilink parsing and vault-aware resolution.

### 3. `IPynbExtractor` (Subclass)
- **File**: `src/syntagmax/extractors/ipynb.py`
- **Inheritance**: `MarkdownExtractor`
- **Responsibility**: Handles `.ipynb` files (Jupyter Notebooks).
- **Implementation**: Extracts markdown from notebook cells and passes it to the base extractor with a `NotebookLocation` builder.

### 4. Grammar Migration
- **Rename**: `src/syntagmax/extractors/obsidian.lark` → `src/syntagmax/extractors/markdown.lark`.
- This reflects that the `[REQ]` syntax is a general standard within Syntagmax, not unique to Obsidian.

## Implementation Details

### Location Builder Signature
```python
def location_builder(start_line: int, end_line: int) -> Location:
    # Implementation provided by subclass
```

### Extractor Methods
- `MarkdownExtractor._extract_from_markdown`: Generic parsing loop.
- `ObsidianExtractor.extract_from_file`: Reads file, creates `LineLocation` builder, calls base.
- `IPynbExtractor.extract_from_file`: Parses JSON, iterates cells, creates `NotebookLocation` builder per cell, calls base.

## Verification Plan
1.  **Unit Tests**:
    - Update `tests/test_extractors.py` to verify `ObsidianExtractor` still works correctly.
    - Update `tests/test_ipynb_extractor.py` to verify `IPynbExtractor` correctly uses `NotebookLocation` and supports multiple artifacts.
2.  **Regression Testing**:
    - Run all existing tests to ensure no breakage in metamodel validation or trace processing.
