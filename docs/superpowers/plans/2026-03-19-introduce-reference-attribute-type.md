# Introduce "reference" Attribute Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the Metamodel DSL and artifact validation to support a new `reference` attribute type that refers to other artifacts.

**Architecture:** Update the Lark grammar and transformer to recognize the `reference` type. Extend `ArtifactValidator._validate_attributes` to verify that reference values are well-formed (`TYPE-ID`) and that the `TYPE` prefix exists in the metamodel.

**Tech Stack:** Python, Lark (Parsing), Pytest (Testing).

---

### Task 1: Update DSL Grammar & Parser

**Files:**
- Modify: `src/syntagmax/metamodel.lark`
- Modify: `src/syntagmax/metamodel.py`
- Modify: `tests/test_metamodel.py`

- [x] **Step 1: Add a failing test for "reference" type parsing**

In `tests/test_metamodel.py`, add:
```python
def test_reference_type_parsing(tmp_path):
    model_content = """
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute link is optional reference
"""
    model_file = tmp_path / "test.model"
    model_file.write_text(model_content)
    errors = []
    model = load_metamodel(model_file, errors, validate=False)
    assert not errors
    assert model['artifacts']['REQ']['attributes']['link']['type_info'] == {'type': 'reference'}
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metamodel.py -v`
Expected: FAIL (Lark parsing error or missing 'reference' type)

- [x] **Step 3: Update `src/syntagmax/metamodel.lark`**

Add `reference` to the `?type` rule:
```lark
?type: "string" -> type_string
     | "integer" -> type_integer
     | "boolean" -> type_boolean
     | "reference" -> type_reference
     | "enum" "[" value ("," value)* "]" -> type_enum
```

- [x] **Step 4: Update `src/syntagmax/metamodel.py`**

Add `type_reference` to `DSLTransformer`:
```python
    def type_reference(self, _):
        return {'type': 'reference'}
```

- [x] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_metamodel.py -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add src/syntagmax/metamodel.lark src/syntagmax/metamodel.py tests/test_metamodel.py
git commit -m "feat: add reference type to metamodel DSL"
```

---

### Task 2: Implement Reference Validation

**Files:**
- Modify: `src/syntagmax/analyse.py`
- Create: `tests/test_reference_validation.py`

- [x] **Step 1: Create failing tests for reference validation**

Create `tests/test_reference_validation.py`:
```python
import pytest
from pathlib import Path
from syntagmax.metamodel import load_metamodel
from syntagmax.analyse import ArtifactValidator
from syntagmax.artifact import Artifact, ARef
from syntagmax.config import Config

@pytest.fixture
def validator(tmp_path):
    model_content = """
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute link is optional reference

artifact SRS:
    attribute id is mandatory string
    attribute contents is mandatory string
"""
    model_file = tmp_path / "test.model"
    model_file.write_text(model_content)
    errors = []
    metamodel = load_metamodel(model_file, errors, validate=True)
    return ArtifactValidator(metamodel)

def test_valid_reference(validator):
    art = Artifact(None)
    art.atype = "REQ"
    art.aid = "1"
    art.fields = {"id": "1", "contents": "test", "link": "SRS-001"}
    errors = validator.validate(art)
    assert not errors

def test_malformed_reference(validator):
    art = Artifact(None)
    art.atype = "REQ"
    art.aid = "1"
    art.fields = {"id": "1", "contents": "test", "link": "INVALID_REF"}
    errors = validator.validate(art)
    assert any("malformed reference" in e.lower() for e in errors)

def test_unknown_type_reference(validator):
    art = Artifact(None)
    art.atype = "REQ"
    art.aid = "1"
    art.fields = {"id": "1", "contents": "test", "link": "XYZ-001"}
    errors = validator.validate(art)
    assert any("unknown artifact type" in e.lower() for e in errors)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reference_validation.py -v`
Expected: FAIL (Attribute 'link' ignored or no validation performed)

- [x] **Step 3: Update `src/syntagmax/analyse.py`**

In `ArtifactValidator._validate_attributes`, add the `reference` check:
```python
            # -- REFERENCE CHECK --
            elif expected_type == 'reference':
                if '-' not in value:
                    self.errors.append(
                        f"Attribute '{name}' value '{value}' is a malformed reference (expected TYPE-ID) ({artifact})"
                    )
                else:
                    ref_atype = value.split('-', 1)[0]
                    if ref_atype not in self._artifacts:
                        self.errors.append(
                            f"Attribute '{name}' value '{value}' refers to an unknown artifact type '{ref_atype}' ({artifact})"
                        )
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reference_validation.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/syntagmax/analyse.py tests/test_reference_validation.py
git commit -m "feat: implement reference attribute validation"
```

---

### Task 3: Documentation & Finalization

**Files:**
- Modify: `README.md`

- [x] **Step 1: Update README.md**

Add `reference` to the "Supported attribute types" list in the "Metamodel DSL" section.

- [x] **Step 2: Run all tests to ensure no regressions**

Run: `pytest`
Expected: All tests PASS

- [x] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document reference attribute type in README"
```
