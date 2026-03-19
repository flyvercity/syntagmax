# Design Spec: Introduce "reference" Attribute Type

## Status: Draft
## Date: 2026-03-19
## Author: Gemini CLI

## 1. Overview
Enhance the Metamodel DSL and artifact validation logic to support a new attribute type: `reference`. This type allows an attribute to store a string that refers to another artifact (e.g., `SRS-001`). Validation will ensure the reference is well-formed and that the referenced artifact type is defined in the metamodel.

## 2. Goals
- Add `reference` as a valid attribute type in the Metamodel DSL.
- Implement validation for `reference` attributes:
    - Must be coercible to `ARef` (format: `TYPE-ID`).
    - The `atype` (type prefix) must exist in the metamodel.
- Update `README.md` to include the new type.
- Add unit tests for both successful and failing validation cases.

## 3. Implementation Plan

### 3.1 DSL Grammar (`src/syntagmax/metamodel.lark`)
- Add `reference` to the `type` rule.
```lark
?type: "string" -> type_string
     | "integer" -> type_integer
     | "boolean" -> type_boolean
     | "reference" -> type_reference
     | "enum" "[" value ("," value)* "]" -> type_enum
```

### 3.2 Metamodel Parsing (`src/syntagmax/metamodel.py`)
- Implement `type_reference` in `DSLTransformer`:
```python
def type_reference(self, _):
    return {'type': 'reference'}
```

### 3.3 Artifact Validation (`src/syntagmax/analyse.py`)
- Update `ArtifactValidator._validate_attributes` to handle `reference` type:
    - Attempt to parse the value using `ARef.coerce` (or simple string split).
    - If parsing fails (no `-` or empty parts), report a "malformed reference" error.
    - Check if the extracted `atype` exists in `self._artifacts` (the metamodel's artifact definitions).
    - If `atype` is unknown, report an "unknown artifact type in reference" error.

## 4. Verification Plan

### 4.1 Unit Tests
- **Metamodel Parsing (`tests/test_metamodel.py`)**:
    - Verify that `attribute link is optional reference` parses correctly into `{'type': 'reference'}`.
- **Artifact Validation (`tests/test_traces.py` or new `tests/test_validation.py`)**:
    - **Valid Reference**: `REQ-1` where `REQ` is defined.
    - **Malformed Reference**: `INVALIDREF` (missing `-`).
    - **Unknown Type**: `XYZ-1` where `XYZ` is not in the metamodel.
    - **Mandatory Check**: Ensure a mandatory `reference` attribute is flagged if missing.

### 4.2 Documentation
- Update `README.md`'s "Metamodel DSL" section to include `reference` in the list of supported types.
