# Markdown Extractor Base Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the extractor architecture to introduce a generic `MarkdownExtractor` base class and decouple `IPynbExtractor` from `ObsidianExtractor`.

**Architecture:** 
1. Move the `[REQ]` grammar to `markdown.lark`.
2. Create a generic `MarkdownExtractor` in `markdown.py` that handles parsing logic.
3. Use a `location_builder` callback to decouple the base class from specific location types.
4. Refactor `ObsidianExtractor` and `IPynbExtractor` to inherit from `MarkdownExtractor`.

**Tech Stack:** Python, Lark, pathlib.

---

### Task 1: Migrate Grammar and Create Markdown Base Class

**Files:**
- Create: `src/syntagmax/extractors/markdown.py`
- Create: `src/syntagmax/extractors/markdown.lark`
- Delete: `src/syntagmax/extractors/obsidian.lark`

- [ ] **Step 1: Move grammar file**
Copy `src/syntagmax/extractors/obsidian.lark` to `src/syntagmax/extractors/markdown.lark` and delete the old one.

- [ ] **Step 2: Create MarkdownExtractor class in `markdown.py`**
Extract symbols from `obsidian.py` and implement the generic extractor.

```python
# src/syntagmax/extractors/markdown.py
from pathlib import Path
import logging as lg
import re
from typing import Callable
from lark import Lark, Transformer, exceptions
from benedict import benedict

from syntagmax.extractors.extractor import Extractor, ExtractorResult
from syntagmax.config import Config, InputRecord
from syntagmax.artifact import ArtifactBuilder, Artifact, Location

class MarkdownArtifact(Artifact):
    def __init__(self, config: Config):
        super().__init__(config)

class MarkdownTransformer(Transformer):
    def AID(self, t): return str(t).lower()
    def content_text(self, t): return str(t[0])
    def yaml_content(self, t): return str(t[0])
    def yaml_block(self, t): return {'text': str(t[0]) if t else ''}
    def contents(self, t): return {'text': str(t[0]) if t else ''}
    def field(self, t): return {'field': {'marker': t[0], 'contents': t[1]}}
    def fields(self, t): return {'list': list(t)}
    def _NL(self, t): return None
    def req(self, t): return {'req': {'contents': t[0], 'fields': t[1], 'yaml': t[2]}}

class MarkdownExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord, metamodel: dict | None = None):
        super().__init__(config, record, metamodel)
        grammar_path = Path(__file__).parent / 'markdown.lark'
        self._parser = Lark.open(grammar_path, rel_to=__file__, parser='lalr', maybe_placeholders=False)
        self._transformer = MarkdownTransformer()

    def _extract_from_markdown(self, filepath: Path, markdown: str, location_builder: Callable[[int, int], Location]) -> ExtractorResult:
        artifacts: list[Artifact] = []
        errors: list[str] = []
        start_marker = re.compile(r'\[REQ\]', re.IGNORECASE)
        pos = 0
        while True:
            match = start_marker.search(markdown, pos)
            if not match: break
            start_pos = match.start()
            yaml_end_marker = '```'
            yaml_start_pos = markdown.find('```yaml', start_pos)
            if yaml_start_pos == -1:
                pos = match.end()
                continue
            end_pos = markdown.find(yaml_end_marker, yaml_start_pos + 7)
            if end_pos == -1:
                pos = yaml_start_pos + 7
                continue
            segment_end = end_pos + len(yaml_end_marker)
            segment = markdown[start_pos:segment_end]
            start_line = markdown.count('\n', 0, start_pos) + 1
            end_line = markdown.count('\n', 0, segment_end) + 1
            try:
                tree = self._parser.parse(segment)
                req_data = self._transformer.transform(tree)
                req = benedict(req_data)
                contents = req.get_str('req.contents.text')
                fields = req.get_list('req.fields.list')
                yaml_text = req.get('req.yaml.text')
                if not yaml_text:
                    errors.append(f'Missing YAML in metadata at line {start_line}')
                    pos = segment_end
                    continue
                yaml_dict = benedict.from_yaml(yaml_text)
                if 'attrs' not in yaml_dict:
                    errors.append(f'Invalid metadata in YAML at line {start_line}')
                    pos = segment_end
                    continue
                yaml_attrs = yaml_dict.get_dict('attrs')
                temp_attrs = {
                    **{field.get_str('field.marker'): field.get_str('field.contents.text').strip() for field in fields},
                    **yaml_attrs,
                }
                aid = temp_attrs.get('id')
                if not aid:
                    errors.append(f'Missing ID in metadata at line {start_line}')
                    pos = segment_end
                    continue
                atype = temp_attrs.get('atype') or self._record.default_atype
                builder = ArtifactBuilder(
                    config=self._config,
                    ArtifactClass=MarkdownArtifact,
                    driver=self.driver(),
                    location=location_builder(start_line, end_line),
                    metamodel=self._metamodel,
                )
                builder.add_id(aid, atype)
                for field in fields:
                    builder.add_field(field.get_str('field.marker'), field.get_str('field.contents.text').strip())
                for name, value in yaml_attrs.items():
                    if isinstance(value, list):
                        for v in value: builder.add_field(name, str(v))
                    else: builder.add_field(name, str(value))
                builder.add_field('contents', contents)
                artifacts.append(builder.build())
            except Exception as e:
                errors.append(f'Error processing requirement at line {start_line}: {e}')
            pos = segment_end
        return artifacts, errors
```

- [ ] **Step 3: Commit**
```bash
git add src/syntagmax/extractors/markdown.*
git rm src/syntagmax/extractors/obsidian.lark
git commit -m "feat: introduce MarkdownExtractor base class"
```

### Task 2: Refactor ObsidianExtractor

**Files:**
- Modify: `src/syntagmax/extractors/obsidian.py`

- [ ] **Step 1: Simplify ObsidianExtractor**
Inherit from `MarkdownExtractor` and remove redundant code.

```python
# src/syntagmax/extractors/obsidian.py
from pathlib import Path
from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.extractors.extractor import ExtractorResult
from syntagmax.artifact import LineLocation

class ObsidianArtifact(MarkdownArtifact): # Optional: keep class name for compatibility
    pass

class ObsidianExtractor(MarkdownExtractor):
    def driver(self) -> str:
        return 'obsidian'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        markdown = filepath.read_text(encoding='utf-8')
        loc_file = self._config.derive_path(filepath)
        
        def location_builder(start, end):
            return LineLocation(loc_file=loc_file, loc_lines=(start, end))
            
        return self._extract_from_markdown(filepath, markdown, location_builder)
```

- [ ] **Step 2: Commit**
```bash
git add src/syntagmax/extractors/obsidian.py
git commit -m "refactor: update ObsidianExtractor to use MarkdownExtractor base"
```

### Task 3: Refactor IPynbExtractor

**Files:**
- Modify: `src/syntagmax/extractors/ipynb.py`

- [ ] **Step 1: Simplify IPynbExtractor**
Inherit from `MarkdownExtractor` directly.

```python
# src/syntagmax/extractors/ipynb.py
from pathlib import Path
import json
import logging as lg
from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.extractors.extractor import ExtractorResult
from syntagmax.artifact import NotebookLocation

class IPynbExtractor(MarkdownExtractor):
    def driver(self) -> str:
        return 'ipynb'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        try:
            notebook = json.loads(filepath.read_text(encoding='utf-8'))
            loc_file = self._config.derive_path(filepath)
            artifacts = []
            errors = []

            for i, cell in enumerate(notebook['cells']):
                if cell['cell_type'] == 'markdown':
                    markdown = ''.join(cell['source'])
                    
                    def location_builder(start, end, idx=i):
                        return NotebookLocation(loc_file=loc_file, loc_lines=(start, end), loc_cell=idx)
                        
                    cell_artifacts, cell_errors = self._extract_from_markdown(filepath, markdown, location_builder)
                    errors.extend(cell_errors)
                    artifacts.extend(cell_artifacts)

            return artifacts, errors
        except Exception as e:
            return [], [f'Error extracting from {filepath}: {e}']
```

- [ ] **Step 2: Commit**
```bash
git add src/syntagmax/extractors/ipynb.py
git commit -m "refactor: update IPynbExtractor to use MarkdownExtractor base"
```

### Task 4: Verification

- [ ] **Step 1: Run all extractor tests**
Run: `uv run pytest tests/test_extractors.py tests/test_ipynb_extractor.py -v`
Expected: ALL PASS

- [ ] **Step 2: Run full suite**
Run: `uv run pytest -v`
Expected: SAME FAILURES AS BEFORE (impact tests), BUT ALL EXTRACTOR TESTS PASS.
