# Comma-Separated YAML Attributes in Markdown/Obsidian Extractor

## Problem Statement

When using the Obsidian/Markdown driver, YAML string values like `parent: parent-a, parent-b, parent-c` are passed as a single string to `add_field`. While `add_field` already splits comma-separated references, it does not split for other `multiple` types (string, enum). The fix should be in the markdown extractor, splitting comma-separated YAML string values into individual `add_field` calls when the metamodel declares the attribute as `multiple`.

## Requirements

- Support comma-separated values in YAML string attributes for all `multiple` attribute types (string, enum, reference)
- Only split when the metamodel declares the attribute as `multiple`
- Single-valued attributes are never split (safe default)
- Change lives in the markdown extractor (before calling `add_field`)

## Background

- The YAML attr processing loop is at line ~308 in `src/syntagmax/extractors/markdown.py`
- At that point, `atype` and `self._metamodel` are available
- The existing `isinstance(value, list)` branch handles YAML list syntax
- The `else` branch passes the raw string to `add_field`
- We need to add comma-splitting in that `else` branch when the attribute is declared `multiple` in the metamodel

## Proposed Solution

In the `else` branch of the YAML attrs loop in `markdown.py`, check if the metamodel declares the attribute as `multiple`. If so, split on comma and call `add_field` for each part. Otherwise, pass the value as-is.

## Task Breakdown

### Task 1: Add a helper method to determine if an attribute is `multiple`

- **Objective:** Add a private method `_is_multiple_attr(self, atype: str, attr_name: str) -> bool` in `MarkdownExtractor` that checks the metamodel.
- **Implementation:** Look up `self._metamodel['artifacts'][atype]['attributes'][attr_name]` and check for `multiple: True` in any rule.
- **Test:** Unit test that the helper returns `True` for a `multiple` attribute and `False` for a non-multiple one.
- **Demo:** Running `uv run pytest tests/test_multiple_attributes_e2e.py` passes (no regressions).

### Task 2: Add comma-splitting logic in the YAML attrs loop

- **Objective:** In the `else` branch (string value from YAML), if the attribute is `multiple` per the metamodel, split on `,` and call `add_field` for each trimmed part.
- **Implementation:** Replace the single `builder.add_field(name, str(value))` call with a check: if `_is_multiple_attr(atype, name)` and `','` is in the string value, split and call `add_field` for each part; otherwise call once as before.
- **Test:** Existing tests still pass.
- **Demo:** Running `uv run pytest` shows no regressions.

### Task 3: Add test for comma-separated YAML string attributes in Obsidian extractor

- **Objective:** Add a test case in `test_multiple_attributes_e2e.py` that verifies comma-separated YAML values are correctly split.
- **Implementation:** Write a test `test_obsidian_extractor_comma_separated_yaml` that creates a markdown file with `tag: tagX, tagY, tagZ` in the YAML attrs block and asserts the resulting field is `['tagX', 'tagY', 'tagZ']`. Also test with a reference type: `parent: REQ-001, REQ-002`.
- **Test:** New test passes.
- **Demo:** `uv run pytest tests/test_multiple_attributes_e2e.py` shows the new test green.

### Task 4: Add test for non-multiple attributes NOT being split

- **Objective:** Ensure single-valued attributes with commas in the value are NOT split.
- **Implementation:** Add a test case where a non-multiple string attribute has a comma in its value (e.g., `priority: high, urgent` where `priority` is `multiple: False`) and assert it remains a single string value.
- **Test:** New test passes.
- **Demo:** `uv run pytest tests/test_multiple_attributes_e2e.py` — all tests green.
