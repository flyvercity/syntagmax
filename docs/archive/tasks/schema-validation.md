# Schema Validation in Metamodel DSL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement validation for the `as <schema>` clause in the metamodel DSL to ensure only valid placeholders (`{atype}`, `{num}`, `{num:padding}`) are used.

**Architecture:** Redefine the grammar to structure the schema string and update the transformer to validate placeholders and raise errors for invalid ones.

**Tech Stack:** Python, Lark (parser).

---

### Task 1: Create failing test case

**Files:**
- Create: `tests/test_metamodel_schema_validation.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pathlib import Path
from syntagmax.metamodel import load_metamodel
from syntagmax.errors import FatalError

def test_invalid_placeholder_validation(tmp_path):
    model = tmp_path / "test.model"
    model.write_text("""
artifact REQ:
    id is string as REQ-{invalid}
    attribute contents is mandatory string
""", encoding='utf-8')
    
    errors = []
    with pytest.raises(FatalError) as excinfo:
        load_metamodel(model, errors)
    
    assert "Invalid placeholder: {invalid}" in str(excinfo.value)

def test_unbalanced_brace_validation(tmp_path):
    model = tmp_path / "test.model"
    model.write_text("""
artifact REQ:
    id is string as REQ-{num:4
    attribute contents is mandatory string
""", encoding='utf-8')
    
    errors = []
    # This will be caught by Lark itself because it won't match the new grammar
    with pytest.raises(FatalError):
        load_metamodel(model, errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metamodel_schema_validation.py -v`
Expected: FAIL (loads successfully, or fails for different reasons)

- [ ] **Step 3: Commit**

```bash
git add tests/test_metamodel_schema_validation.py
git commit -m "test: add failing test cases for schema validation"
```

---

### Task 2: Update Grammar

**Files:**
- Modify: `src/syntagmax/metamodel.lark`

- [ ] **Step 1: Modify `schema_value` and add supporting rules**

Change the `?schema_value` rule and remove `SCHEMA`. Add `unquoted_items`, `quoted_items`, `placeholder`, `invalid_placeholder`, `SCHEMA_PART`, and `QUOTED_PART`. Import `INT`.

```lark
# ...
rule: "attribute" name "is" PRESENCE [MULTIPLE] type _NL
    | "id" "is" type ["as" schema_value] _NL
# ...
?schema_value: unquoted_items | quoted_items

unquoted_items: (SCHEMA_PART | placeholder | invalid_placeholder)+
quoted_items: "\"" (QUOTED_PART | placeholder | invalid_placeholder)* "\""

placeholder: "{" ( "atype" | "num" [ ":" INT ] ) "}"
invalid_placeholder: "{" /[^}]*/ "}"

SCHEMA_PART: /[^ \t\n\r"{]+/
QUOTED_PART: /[^"{]+/

%import common.INT
# ...
```

- [ ] **Step 2: Commit**

```bash
git add src/syntagmax/metamodel.lark
git commit -m "feat: redefine schema grammar to support validation"
```

---

### Task 3: Update Transformer

**Files:**
- Modify: `src/syntagmax/metamodel.py`

- [ ] **Step 1: Add transformer methods**

Add `unquoted_items`, `quoted_items`, `placeholder`, and `invalid_placeholder` methods to `DSLTransformer`. Update `rule` method to stop stripping quotes (handled by `quoted_items`).

```python
    # Inside DSLTransformer class
    def unquoted_items(self, children):
        return "".join(map(str, children))

    def quoted_items(self, children):
        # We need to strip the quotes if they were included by the rule?
        # quoted_items: "\"" (QUOTED_PART | placeholder | invalid_placeholder)* "\""
        # The children will be only the items inside the quotes because "\"" are literal strings in the rule.
        return "".join(map(str, children))

    def placeholder(self, children):
        if str(children[0]) == "atype":
            return "{atype}"
        else:
            # it's num
            if len(children) > 1 and children[1] is not None:
                return f"{{num:{children[1]}}}"
            return "{num}"

    def invalid_placeholder(self, children):
        content = str(children[0])
        raise ValueError(f"Invalid placeholder: {{{content}}}")
```

Update `rule` to use `children[1]` directly:

```python
        # Handle the "id" rule
        else:
            # children: type_info, [schema]
            schema = children[1] if len(children) > 1 and children[1] is not None else None
            return {
                'name': 'id',
                'presence': 'mandatory',
                'multiple': False,
                'type_info': children[0],
                'schema': schema,
                'id_rule': True,
            }
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_metamodel_schema_validation.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/syntagmax/metamodel.py
git commit -m "feat: implement schema validation in transformer"
```

---

### Task 4: Add positive tests

**Files:**
- Modify: `tests/test_metamodel_schema_validation.py`

- [ ] **Step 1: Add success test cases**

```python
def test_valid_placeholders(tmp_path):
    model = tmp_path / "test.model"
    model.write_text("""
artifact REQ:
    id is string as REQ-{atype}-{num:4}
    attribute contents is mandatory string
""", encoding='utf-8')
    
    errors = []
    mm = load_metamodel(model, errors)
    assert mm['artifacts']['REQ']['attributes']['id']['schema'] == "REQ-{atype}-{num:4}"

def test_quoted_schema_with_spaces(tmp_path):
    model = tmp_path / "test.model"
    model.write_text("""
artifact REQ:
    id is string as "Project REQ-{num:3}"
    attribute contents is mandatory string
""", encoding='utf-8')
    
    errors = []
    mm = load_metamodel(model, errors)
    assert mm['artifacts']['REQ']['attributes']['id']['schema'] == "Project REQ-{num:3}"
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/test_metamodel_schema_validation.py tests/test_metamodel.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_metamodel_schema_validation.py
git commit -m "test: add success test cases for schema validation"
```
