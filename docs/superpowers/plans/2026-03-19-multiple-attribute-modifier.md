# Multiple Attribute Modifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the DSL and extraction logic to support a "multiple" modifier for artifact attributes, allowing them to store and validate lists of values.

**Architecture:** Update the metamodel to recognize the "multiple" modifier, pass the metamodel to extractors, and use a centralized `ArtifactBuilder` to handle multiplicity logic. Validation is updated to ensure values match the metamodel's multiplicity constraints.

**Tech Stack:** Python, Lark (Parsing), Benedict (Dict utility), Pytest.

---

### Task 1: Update Metamodel DSL and Loader

**Files:**
- Modify: `src/syntagmax/metamodel.lark`
- Modify: `src/syntagmax/metamodel.py`
- Test: `tests/test_metamodel.py`

- [ ] **Step 1: Update `metamodel.lark` to support `multiple` keyword**
```lark
rule: "attribute" name "is" PRESENCE [MULTIPLE] type _NL
MULTIPLE: "multiple"
```

- [ ] **Step 2: Update `DSLTransformer.rule` in `metamodel.py`**
```python
    def rule(self, children):
        name = str(children[0])
        presence = str(children[1])
        multiple = False
        type_info = children[-1]
        if any(isinstance(c, str) and c == 'multiple' for c in children):
            multiple = True
        return {'name': name, 'presence': presence, 'multiple': multiple, 'type_info': type_info}
```

- [ ] **Step 3: Add test for `multiple` keyword in `tests/test_metamodel.py`**
- [ ] **Step 4: Verify tests pass**

---

### Task 2: Enhance Artifact and ArtifactBuilder

**Files:**
- Modify: `src/syntagmax/artifact.py`

- [ ] **Step 1: Update `Artifact.fields` type hint**
```python
        self.fields: dict[str, str | list[str]] = {}
```

- [ ] **Step 2: Update `ArtifactBuilder.__init__` to accept `metamodel`**
```python
    def __init__(self, config: Config, ArtifactClass: type[Artifact], driver: str, location: Location, metamodel: dict | None = None):
        self.artifact = ArtifactClass(config)
        self.artifact.driver = driver
        self.artifact.location = location
        self._metamodel = metamodel
```

- [ ] **Step 3: Update `ArtifactBuilder.add_field` to handle multiplicity**
```python
    def add_field(self, field: str, value: str):
        multiple = False
        if self._metamodel and self.artifact.atype in self._metamodel.get('artifacts', {}):
            rules = self._metamodel['artifacts'][self.artifact.atype]['attributes']
            if field in rules:
                multiple = rules[field].get('multiple', False)

        if multiple:
            if field not in self.artifact.fields:
                self.artifact.fields[field] = []
            if not isinstance(self.artifact.fields[field], list):
                 self.artifact.fields[field] = [str(self.artifact.fields[field])]
            self.artifact.fields[field].append(value)
        else:
            if field in self.artifact.fields:
                raise ValidationError(self._build_error(f'Duplicate field: {field}'))
            self.artifact.fields[field] = value
        return self
```

- [ ] **Step 4: Update `ArtifactBuilder.build` to initialize optional multiple fields**
```python
    def build(self) -> Artifact:
        # ... existing checks ...
        if self._metamodel and self.artifact.atype in self._metamodel.get('artifacts', {}):
            rules = self._metamodel['artifacts'][self.artifact.atype]['attributes']
            for name, rule in rules.items():
                if rule.get('multiple') and name not in self.artifact.fields:
                    self.artifact.fields[name] = []
        return self.artifact
```

---

### Task 3: Update Extractor Interface and Extraction Flow

**Files:**
- Modify: `src/syntagmax/extractors/extractor.py`
- Modify: `src/syntagmax/extract.py`

- [ ] **Step 1: Update `Extractor.__init__`**
```python
    def __init__(self, config: Config, record: InputRecord, metamodel: dict | None = None):
        self._config = config
        self._record = record
        self._metamodel = metamodel
```

- [ ] **Step 2: Update `extract()` in `extract.py` to pass metamodel**
```python
def extract(config: Config) -> tuple[dict[ARef, Artifact], list[str]]:
    # ...
    for record in config.input_records():
        extractor = EXTRACTORS[record.driver](config, record, config.metamodel)
        # ...
```

---

### Task 4: Update TextExtractor and text.lark

**Files:**
- Modify: `src/syntagmax/extractors/text.lark`
- Modify: `src/syntagmax/extractors/text.py`

- [ ] **Step 1: Update `text.lark` to support arbitrary attributes**
```lark
directive: id_directive | type_directive | attr_directive
attr_directive: NAME "=" VALUE
NAME: /[a-zA-Z0-9_-]+/
VALUE: /[^ \t\n\r>\[\]]+/
```

- [ ] **Step 2: Update `TextTransformer` and `TextExtractor` to use `add_field`**
- [ ] **Step 3: Update `TextExtractor.extract_from_file` to pass `self._metamodel` to `ArtifactBuilder`**

---

### Task 5: Update ObsidianExtractor

**Files:**
- Modify: `src/syntagmax/extractors/obsidian.py`

- [ ] **Step 1: Update `ObsidianExtractor.extract_from_markdown`**
- [ ] **Step 2: Use `builder.add_field` for each field and YAML attribute instead of bulk `add_fields`**

---

### Task 6: Update Validation Logic

**Files:**
- Modify: `src/syntagmax/analyse.py`

- [ ] **Step 1: Update `_validate_attributes` to handle lists**
- [ ] **Step 2: Implement multiplicity checks (multiple attributes MUST be lists, non-multiple MUST NOT)**
- [ ] **Step 3: Ensure type checks (integer, boolean, reference, enum) work on list elements**

---

### Task 7: Comprehensive Testing and Documentation

**Files:**
- Create: `tests/test_multiple_attributes.py`
- Modify: `README.md`

- [ ] **Step 1: Create `tests/test_multiple_attributes.py` with end-to-end tests**
- [ ] **Step 2: Update `README.md` with "multiple" modifier documentation**
- [ ] **Step 3: Run all tests and verify everything passes**
