# Introduce "reference to parent" Attribute Modifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the Metamodel DSL to support `reference to parent` and use it to build the artifact hierarchy, removing hardcoded `pid` logic.

**Architecture:** Update the Lark grammar and transformer to recognize the `to parent` modifier. Implement a `populate_pids` phase in `tree.py` that uses metamodel rules to fill `Artifact.pids`.

**Tech Stack:** Python, Lark (Parsing), Pytest.

---

### Task 1: Update Metamodel Grammar

**Files:**
- Modify: `src/syntagmax/metamodel.lark`

- [ ] **Step 1: Update `type_reference` rule**

```lark
# src/syntagmax/metamodel.lark
?type: "string" -> type_string
     | "integer" -> type_integer
     | "boolean" -> type_boolean
     | "reference" ["to" "parent"] -> type_reference
     | "enum" "[" value ("," value)* "]" -> type_enum
```

- [ ] **Step 2: Commit grammar changes**

```bash
git add src/syntagmax/metamodel.lark
git commit -m "dsl: add 'to parent' modifier to reference type in grammar"
```

---

### Task 2: Update Metamodel Transformer

**Files:**
- Modify: `src/syntagmax/metamodel.py`
- Test: `tests/test_metamodel.py`

- [ ] **Step 1: Add failing test for parsing `reference to parent`**

```python
# tests/test_metamodel.py
def test_reference_to_parent_parsing(tmp_path):
    model_content = """
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute mainpid is mandatory reference to parent
    attribute link is optional reference
"""
    model_file = tmp_path / "test_parent.model"
    model_file.write_text(model_content)
    errors = []
    from syntagmax.metamodel import load_metamodel
    model = load_metamodel(model_file, errors, validate=False)
    assert not errors
    attrs = model['artifacts']['REQ']['attributes']
    assert attrs['mainpid']['type_info'] == {'type': 'reference', 'to_parent': True}
    assert attrs['link']['type_info'] == {'type': 'reference', 'to_parent': False}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metamodel.py::test_reference_to_parent_parsing -v`
Expected: FAIL (AssertionError or TypeError because `type_reference` doesn't handle children yet)

- [ ] **Step 3: Update `DSLTransformer.type_reference`**

```python
# src/syntagmax/metamodel.py
    def type_reference(self, children):
        # Lark passes literal strings as children if they are in the rule
        to_parent = any(str(c) == 'to' for c in children)
        return {'type': 'reference', 'to_parent': to_parent}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_metamodel.py::test_reference_to_parent_parsing -v`
Expected: PASS

- [ ] **Step 5: Commit transformer changes**

```bash
git add src/syntagmax/metamodel.py tests/test_metamodel.py
git commit -m "feat: handle 'to parent' modifier in metamodel transformer"
```

---

### Task 3: Remove Hardcoded `pid` Logic

**Files:**
- Modify: `src/syntagmax/artifact.py`

- [ ] **Step 1: Remove `pid` check in `ArtifactBuilder.add_field`**

```python
# src/syntagmax/artifact.py
# Find and remove:
#        if field.lower() == 'pid':
#            try:
#                self.artifact.pids.append(ARef.coerce(value))
#            except Exception:
#                pass
```

- [ ] **Step 2: Run existing tests to see what breaks**

Run: `pytest tests/test_multiplicity_validation.py tests/test_reference_validation.py -v`
(Some tests might fail if they rely on implicit `pid` handling)

- [ ] **Step 3: Commit removal**

```bash
git add src/syntagmax/artifact.py
git commit -m "refactor: remove hardcoded pid-to-parent logic"
```

---

### Task 4: Implement `populate_pids` and Update Tree Building

**Files:**
- Modify: `src/syntagmax/tree.py`
- Modify: `src/syntagmax/main.py`
- Test: `tests/test_metamodel_pids.py` (New)

- [ ] **Step 1: Create `populate_pids` in `src/syntagmax/tree.py`**

```python
# src/syntagmax/tree.py
def populate_pids(config: Config, artifacts: ArtifactMap):
    if not config.metamodel:
        return

    for a in artifacts.values():
        if a.atype not in config.metamodel['artifacts']:
            continue
            
        rules = config.metamodel['artifacts'][a.atype]['attributes']
        for attr_name, rule in rules.items():
            type_info = rule.get('type_info', {})
            if type_info.get('type') == 'reference' and type_info.get('to_parent'):
                val = a.fields.get(attr_name)
                if not val:
                    continue
                
                refs = val if rule.get('multiple') else [val]
                for ref_str in refs:
                    try:
                        ref = ARef.coerce(ref_str)
                        if ref not in a.pids:
                            a.pids.append(ref)
                    except Exception:
                        pass
```

- [ ] **Step 2: Update `process` in `src/syntagmax/main.py` to call `populate_pids`**

```python
# src/syntagmax/main.py
from syntagmax.tree import build_tree, populate_pids # Update import

# In process() function:
    artifacts, e_errors = extract(config)
    errors.extend(e_errors)
    populate_pids(config, artifacts) # Add this line
    t_errors = build_tree(config, artifacts)
```

- [ ] **Step 3: Create E2E test for PID population**

```python
# tests/test_metamodel_pids.py
import pytest
from syntagmax.artifact import Artifact, ARef
from syntagmax.tree import populate_pids
from syntagmax.config import Config
from syntagmax.params import Params

def test_populate_pids_from_metamodel():
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'mainpid': {'name': 'mainpid', 'multiple': False, 'type_info': {'type': 'reference', 'to_parent': True}},
                    'pids': {'name': 'pids', 'multiple': True, 'type_info': {'type': 'reference', 'to_parent': True}},
                    'link': {'name': 'link', 'multiple': False, 'type_info': {'type': 'reference', 'to_parent': False}}
                }
            }
        }
    }
    
    class MockConfig:
        def __init__(self, mm):
            self.metamodel = mm
            
    config = MockConfig(metamodel)
    
    art = Artifact(None)
    art.atype = 'REQ'
    art.fields = {
        'mainpid': 'SRS-1',
        'pids': ['SRS-2', 'SRS-3'],
        'link': 'REQ-2'
    }
    
    artifacts = {ARef('REQ', '1'): art}
    populate_pids(config, artifacts)
    
    expected_pids = [ARef('SRS', '1'), ARef('SRS', '2'), ARef('SRS', '3')]
    assert len(art.pids) == 3
    for p in expected_pids:
        assert p in art.pids
    assert ARef('REQ', '2') not in art.pids
```

- [ ] **Step 4: Run the test**

Run: `pytest tests/test_metamodel_pids.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/syntagmax/tree.py src/syntagmax/main.py tests/test_metamodel_pids.py
git commit -m "feat: populate artifact pids from metamodel rules"
```

---

### Task 5: Documentation Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update Metamodel section in README.md**

Add description of `reference to parent` modifier and explain that it replaces implicit `pid` handling.

- [ ] **Step 2: Commit documentation**

```bash
git add README.md
git commit -m "docs: update README with 'reference to parent' syntax"
```
