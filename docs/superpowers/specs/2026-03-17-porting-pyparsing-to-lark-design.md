# Spec: Porting pyparsing to Lark

## Goal
The goal of this task is to port the remaining `pyparsing` grammars in the project to `lark`. This will unify the parsing libraries used in the codebase and simplify maintenance.

## Background
Currently, the project uses `lark` for its metamodel DSL (`metamodel.py` and `metamodel.lark`) and `pyparsing` for extracting artifacts from text files (`text.py`) and Obsidian notes (`obsidian.py`). The objective is to move all parsing logic to `lark`.

## Proposed Design

### Components

#### 1. Text Extractor (`src/syntagmax/extractors/text.py`)
- **Grammar**: A new `text.lark` file will be created in `src/syntagmax/extractors/`.
- **Parsing**: The `TextExtractor` will continue to find segments starting with `[<`. Once a segment is found, it will use `lark.Lark` to parse the segment contents.
- **Transformation**: A `lark.Transformer` will be implemented in `text.py` to convert the `lark` parse tree into the internal `Ref` objects (`IdRef`, `ATypeRef`, `PidRef`).

#### 2. Obsidian Extractor (`src/syntagmax/extractors/obsidian.py`)
- **Grammar**: A new `obsidian.lark` file will be created in `src/syntagmax/extractors/`.
- **Parsing**: The `ObsidianExtractor` will search for `[REQ]` markers. The `lark` grammar will define the structure of the requirement, including contents, fields, and the YAML block.
- **Transformation**: A `lark.Transformer` will be used to extract the fields and YAML contents from the parse tree.

#### 3. Metamodel DSL (`src/syntagmax/metamodel.py`)
- This file already uses `lark` and will remain largely unchanged, though we might want to ensure consistency in how `lark` parsers are initialized across the project.

#### 4. Dependency Management (`pyproject.toml`)
- The `pyparsing` dependency will be removed from `pyproject.toml`.

### Data Flow

1.  **Extraction Process**:
    - The extractor reads the file contents.
    - It searches for the start of an artifact segment (e.g., `[<` or `[REQ]`).
    - It extracts the substring containing the segment (until the end marker like `>]` or the end of the YAML block).
    - It passes the substring to the `lark` parser.
    - The `lark` transformer converts the parse tree into structured data.
    - The `ArtifactBuilder` uses this data to create `Artifact` objects.

### Error Handling
- `lark.exceptions.ParseError` and `lark.exceptions.UnexpectedToken` will be caught and converted into the existing error reporting format used by the extractors.

### Testing Strategy
- **Baseline Tests**: If there are existing tests, they will be run to establish a baseline.
- **New Tests**: Unit tests will be added/updated for `TextExtractor` and `ObsidianExtractor` to verify that the new `lark`-based implementation correctly extracts data from various valid and invalid inputs.
- **Comparison**: For each extractor, we will ensure that the extracted fields (IDs, types, parent IDs, attributes) match the expected output.

## Success Criteria
- All `pyparsing` imports and usages are removed from the codebase.
- `pyparsing` is removed from `pyproject.toml`.
- All artifact extraction tests pass with the new `lark`-based implementation.
- The project's metamodel DSL continues to work correctly.
