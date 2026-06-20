# Publish System - Block Tree Implementation Spec

## Problem Statement

The current extraction pipeline only produces artifacts, discarding non-requirement text. We need an intermediate "block tree" representation that preserves both artifact blocks and surrounding text, ordered by file and position. A new `publish` command will render this block tree into a single structured markdown document.

## Requirements

1. Block tree preserves the structure of inputs: ROOT → Input Records → Blocks (Text/Artifact)
2. Files within each record sorted lexicographically by relative path to record base
3. Blocks within each file in natural (positional) order
4. All drivers participate (obsidian/markdown, text, sidecar, ipynb)
5. Artifacts rendered in normalized markdown format (heading + body + metadata table)
6. Text blocks rendered as-is
7. New CLI command: `publish <output-file>` reusing `.syntagmax/config.toml`
8. Block tree is NOT used for analysis (impact/metrics/ai) — only for publishing

## Design Decisions

- **Text blocks**: Split at artifact boundaries — each contiguous chunk of non-artifact text becomes its own TextBlock (preserves interleaving order)
- **Published output structure**: Flat sections per input — a heading per input record, then blocks rendered sequentially
- **Config**: Reuse existing `.syntagmax/config.toml` for knowing which inputs to process
- **Artifact rendering**: Normalized markdown format — `### AID` heading + body text + metadata table (field/value)
- **All drivers included**: obsidian/markdown, text, sidecar, and ipynb from the start
- **Sort order**: By relative path to the record's base directory (lexicographic)

## Artifact Rendering Format

```markdown
### REQ-001

The flight computer software shall implement...

| Field | Value |
|-------|-------|
| parent | SYS-001 |
| status | active |
| priority | critical |
```

## Block Tree Data Model

```
BlockTree
  └── InputBlock (one per input record)
       ├── name: str (input record name)
       └── files: list[FileRecord]
            ├── path: str (relative path)
            └── blocks: list[Block]
                 ├── TextBlock(content: str)
                 └── ArtifactBlock(artifact: Artifact, raw_text: str)
```

## Background / Current Architecture

- Extractors use `extract_from_file()` which scans for markers and returns only `Artifact` objects
- Text extractor uses `[< ... >]` markers with explicit position tracking (`start_pos`, `segment_end`)
- Markdown/obsidian extractor uses `[MARKER]...```yaml...```/[/MARKER]` markers with position tracking
- Sidecar extractor treats each file as one artifact (binary file + YAML metadata)
- IPynb extractor iterates cells, extracting from markdown cells
- `InputRecord.filepaths` comes from `Path.glob()` — unsorted

## Task Breakdown

### Task 1: Define the Block Tree data model

- Create `src/syntagmax/blocks.py` with `Block`, `TextBlock`, `ArtifactBlock`, `FileRecord`, `InputBlock`, and `BlockTree` dataclasses.
- `TextBlock` holds raw text content.
- `ArtifactBlock` holds the extracted `Artifact` plus its raw source text.
- `FileRecord` holds a list of blocks for one file.
- `InputBlock` holds a list of `FileRecord`s for one input record.
- `BlockTree` holds a list of `InputBlock`s.
- Test: Unit test that constructs a BlockTree programmatically and verifies structure.
- Demo: `uv run pytest tests/test_blocks.py` passes with basic model instantiation tests.

### Task 2: Add `extract_blocks_from_file()` to the text extractor

- Add a method to `TextExtractor` that returns `list[Block]` — interleaving `TextBlock` and `ArtifactBlock` for the given file. Reuse existing parsing logic but track positions to capture text gaps.
- Test: Write a test with a file containing text → artifact → text → artifact → text, verify correct block sequence and content.
- Demo: `uv run pytest tests/test_blocks.py` passes with text extractor block extraction tests.

### Task 3: Add `extract_blocks_from_file()` to the markdown/obsidian extractor

- Same approach for `MarkdownExtractor` / `ObsidianExtractor`. Track positions between `[MARKER]` segments to capture surrounding markdown text.
- Test: Test with an obsidian-style file with heading text, requirement, more text, another requirement.
- Demo: `uv run pytest tests/test_blocks.py` passes with markdown block extraction tests.

### Task 4: Add `extract_blocks_from_file()` to sidecar and ipynb extractors

- For sidecar, the whole file is one artifact block (no text blocks).
- For ipynb, iterate cells and treat non-artifact markdown cells (and code cells) as text blocks.
- Test: Test sidecar produces a single ArtifactBlock. Test ipynb produces interleaved text/artifact blocks from cells.
- Demo: `uv run pytest tests/test_blocks.py` passes for all drivers.

### Task 5: Build the BlockTree from config

- Create a function `build_block_tree(config: Config) -> BlockTree` in `src/syntagmax/publish.py` that iterates input records, sorts filepaths by relative path, calls `extract_blocks_from_file()` on each, and assembles the tree.
- Test: Integration test using a temp directory with multiple input records and files, verify tree structure and sort order.
- Demo: `uv run pytest tests/test_publish.py` passes.

### Task 6: Render BlockTree to markdown

- Create `render_block_tree(tree: BlockTree) -> str` in `publish.py` that produces the structured markdown output.
- Each input record gets a `## heading`.
- Artifact blocks rendered as `### AID` + body + metadata table.
- Text blocks rendered verbatim.
- Test: Test render output matches expected markdown structure.
- Demo: `uv run pytest tests/test_publish.py` passes with rendering tests.

### Task 7: Add the `publish` CLI command

- Add `publish` command to `cli.py` that takes an output file argument, builds the block tree, renders it, and writes to the output file. Reuses the existing config file option.
- Test: End-to-end test using the example project (`example/obsidian-driver`).
- Demo: `uv run syntagmax publish output.md --cwd ./example/obsidian-driver` produces a valid markdown file combining all inputs.
