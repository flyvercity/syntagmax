# IPynb Extractor Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `IPynbExtractor` to fix a critical interface bug, allow multiple artifacts per notebook, and introduce `NotebookLocation` for better traceability.

**Architecture:** 
1. Introduce `NotebookLocation` in `src/syntagmax/artifact.py`.
2. Update `ObsidianExtractor._extract_from_markdown` to accept an optional `cell_index` and use it for location.
3. Update `IPynbExtractor` to pass proper `Path` objects and `cell_index`.
4. Remove the artificial one-artifact-per-file limit in `IPynbExtractor`.

**Tech Stack:** Python, pathlib, json, lark (via ObsidianExtractor).

---

### Task 1: Introduce NotebookLocation

**Files:**
- Modify: `src/syntagmax/artifact.py`

- [ ] **Step 1: Add NotebookLocation class**

```python
class NotebookLocation(LineLocation):
    def __init__(self, loc_file: str, loc_lines: tuple[int, int], loc_cell: int):
        super().__init__(loc_file, loc_lines)
        self.loc_cell = loc_cell

    def __str__(self) -> str:
        return f'{self.loc_file}[{self.loc_cell}]:{self.loc_lines[0]}-{self.loc_lines[1]}'
```

- [ ] **Step 2: Commit**

```bash
git add src/syntagmax/artifact.py
git commit -m "feat: add NotebookLocation for ipynb support"
```

### Task 2: Update ObsidianExtractor to support cell_index

**Files:**
- Modify: `src/syntagmax/extractors/obsidian.py`

- [ ] **Step 1: Update _extract_from_markdown signature and logic**

Modify `_extract_from_markdown` to accept `cell_index: int | None = None`.
Update the location creation logic:

```python
    def _extract_from_markdown(self, filepath: Path, markdown: str, cell_index: int | None = None) -> ExtractorResult:
        # ...
                loc_file = self._config.derive_path(filepath)
                if cell_index is not None:
                    location = NotebookLocation(
                        loc_file=loc_file, loc_lines=(start_line, end_line), loc_cell=cell_index
                    )
                else:
                    location = LineLocation(loc_file=loc_file, loc_lines=(start_line, end_line))

                builder = ArtifactBuilder(
                    config=self._config,
                    ArtifactClass=ObsidianArtifact,
                    driver=self.driver(),
                    location=location,
                    metamodel=self._metamodel,
                )
```

- [ ] **Step 2: Commit**

```bash
git add src/syntagmax/extractors/obsidian.py
git commit -m "refactor: allow cell_index in ObsidianExtractor._extract_from_markdown"
```

### Task 3: Update IPynbExtractor

**Files:**
- Modify: `src/syntagmax/extractors/ipynb.py`

- [ ] **Step 1: Update extraction logic**

```python
    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        try:
            notebook = json.loads(filepath.read_text(encoding='utf-8'))
            artifacts: list[Artifact] = []
            errors: list[str] = []

            for i, cell in enumerate(notebook['cells']):
                if cell['cell_type'] == 'markdown':
                    markdown = ''.join(cell['source'])
                    cell_artifacts, cell_errors = self._extract_from_markdown(filepath, markdown, cell_index=i)
                    errors.extend(cell_errors)
                    artifacts.extend(cell_artifacts)

            return artifacts, errors
        # ... rest remains same
```

- [ ] **Step 2: Commit**

```bash
git add src/syntagmax/extractors/ipynb.py
git commit -m "feat: update IPynbExtractor to support multiple artifacts and NotebookLocation"
```

### Task 4: Verify with tests

**Files:**
- Modify: `tests/test_ipynb_extractor.py`

- [ ] **Step 1: Update test expectations**

```python
    assert len(errors) == 0
    assert len(artifacts) == 2
    
    assert artifacts[0].aid == 'REQ-IPY-1'
    assert artifacts[1].aid == 'REQ-IPY-2'
    
    # Check locations
    assert str(artifacts[0].location) == 'test.ipynb[0]:1-7'
    assert str(artifacts[1].location) == 'test.ipynb[2]:1-7'
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_ipynb_extractor.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_ipynb_extractor.py
git commit -m "test: update ipynb extractor tests"
```
