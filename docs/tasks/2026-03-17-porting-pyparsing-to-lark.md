# Porting pyparsing to Lark Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unified parsing library (Lark) for all extractors and metamodel.

**Architecture:** 
- External `.lark` grammar files for each extractor.
- `lark.Transformer` for data extraction.
- Minimal manual searching for segment starts.

**Tech Stack:** Lark, Python, benedict.

---

### Task 1: Setup and Baseline

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_extractors.py` (Create)

- [ ] **Step 1: Create a baseline test for TextExtractor**
Create `tests/test_extractors.py` with some sample input and verify current extraction works (if possible). Actually, I'll just write the tests for the NEW implementation and ensure they cover what the OLD implementation did.

- [ ] **Step 2: Commit baseline**
```bash
git add tests/test_extractors.py
git commit -m "test: add baseline tests for extractors"
```

### Task 2: Port TextExtractor

**Files:**
- Create: `src/syntagmax/extractors/text.lark`
- Modify: `src/syntagmax/extractors/text.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Define text.lark grammar**
```lark
?start: header body?

header: (directive)*
directive: id_directive | type_directive

id_directive: "ID" "=" AID
type_directive: "TYPE" "=" ATYPE

AID: /[a-zA-Z0-9-]+/
ATYPE: /[a-zA-Z0-9]+/
REVISION: /[a-zA-Z0-9]+/

body: ">>>" /(.|\n)*/

%import common.WS
%ignore WS
```
Wait, the grammar needs to handle the `HeaderSkip` and `BodySkip` from the original.
Actually, the original `Section` was: `Begin + Header + HeaderSkip + BodyStart + BodySkip + End`.
I'll refine the grammar.

- [ ] **Step 2: Update TextExtractor to use Lark**
Replace `pyparsing` with `lark`. Implement `TextTransformer`.

- [ ] **Step 3: Run tests and verify**
`pytest tests/test_extractors.py`

- [ ] **Step 4: Commit**
```bash
git add src/syntagmax/extractors/text.lark src/syntagmax/extractors/text.py
git commit -m "feat: port TextExtractor to Lark"
```

### Task 3: Port ObsidianExtractor

**Files:**
- Create: `src/syntagmax/extractors/obsidian.lark`
- Modify: `src/syntagmax/extractors/obsidian.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Define obsidian.lark grammar**
```lark
?start: contents fields yaml_block

contents: /(.|\n)*?(?=\[|$|```yaml)/
fields: field*
field: "[" AID "]" contents
yaml_block: "```yaml" /(.|\n)*?/ "```"

AID: /[a-zA-Z0-9_]+/
```
(I'll refine this based on the actual `pyparsing` logic)

- [ ] **Step 2: Update ObsidianExtractor to use Lark**
Replace `pyparsing` with `lark`. Implement `ObsidianTransformer`.

- [ ] **Step 3: Run tests and verify**
`pytest tests/test_extractors.py`

- [ ] **Step 4: Commit**
```bash
git add src/syntagmax/extractors/obsidian.lark src/syntagmax/extractors/obsidian.py
git commit -m "feat: port ObsidianExtractor to Lark"
```

### Task 4: Cleanup

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Remove pyparsing dependency**
```bash
# Edit pyproject.toml and remove "pyparsing>=3.2.3"
```

- [ ] **Step 2: Update lock file**
```bash
uv lock
```

- [ ] **Step 3: Verify everything still works**
`pytest`

- [ ] **Step 4: Commit**
```bash
git add pyproject.toml uv.lock
git commit -m "chore: remove pyparsing dependency"
```
