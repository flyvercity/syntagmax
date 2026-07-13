# Spec: Attribute Presence Mode for Publishing

## Problem Statement

The publish renderer currently only outputs attributes that have actual values. For compliance and traceability documents, users need control over whether all metamodel-defined attributes are rendered (with empty cells for missing values), only mandatory attributes, or only those with real values. This setting must be configurable both globally and per render section, and must respect metamodel conditions when evaluating mandatory status.

## Requirements

1. Add a global `attribute_presence` setting in the publish config with values: `all`, `mandatory`, `values-only`. Default: `values-only` (to preserve backward compatibility).
2. Add a per-section `attribute_presence` field on `TableSection` only (optional, overrides the global when set). The `TextSection` does not support this setting because empty text attributes produce no useful output.
3. Only attributes explicitly listed in the `render` section are considered; the setting filters them by presence:
   - `all`: render all listed attributes regardless of value presence.
   - `mandatory`: render listed attributes that are mandatory in the metamodel (with condition evaluation) OR that have values.
   - `values-only`: render listed attributes only when they have values (current behavior).
4. For table sections: attributes without values render as an empty cell (`| Alias | |`).
5. For text sections: attributes without values are always skipped regardless of the global mode (empty bold label with no text is not useful).
6. Condition evaluation for `mandatory` mode: a conditional mandatory attribute (e.g., `attribute parent is mandatory reference to parent if not derive`) is mandatory only when its condition holds for the specific artifact being rendered.
7. Edge case: if no metamodel is available for an artifact type, `mandatory` degrades to `values-only`; `all` renders all listed attributes regardless. A warning is logged when this degradation occurs.
8. The fallback renderer (`render_artifact_fallback`) is not affected by this feature — it has no explicit attribute list and renders whatever fields exist. This is by design; only explicitly configured render sections support presence filtering.
9. The Pydantic field must use a hyphenated alias (`attribute-presence`) to match existing config conventions (e.g., `table-spacer`, `docx-template`).

## Background

- `PublishConfig` is a Pydantic model in `publish_config.py` with global settings (`start_level`, `table_spacer`, etc.) and a `render` section mapping artifact types to rendering rules.
- `TableSection` and `TextSection` define attribute lists for custom rendering. Both iterate over their `attributes` list and call `get_artifact_field_value()`, skipping entries where the return is `None`.
- The metamodel stores attribute rules as a list of dicts per attribute name, each with `presence` (`mandatory`/`optional`), optional `condition` (`{'anchor': str, 'negated': bool}`), and `type_info`.
- Boolean anchor fields are evaluated as truthy/falsy to determine if a condition holds. Custom boolean values (`true_kw`/`false_kw`) map to truthy/falsy via the metamodel's boolean_values definition.
- `render_block` in `publish.py` handles artifact rendering with explicit render sections. The `RenderContext` holds `config` which has `config.metamodel`.
- The fallback renderer (`render_artifact_fallback`) is not affected by this feature — it has no explicit attribute list and renders whatever fields exist.

## Proposed Solution

### Architecture

1. Define `AttributePresence = Literal['all', 'mandatory', 'values-only']` type alias.
2. Add `attribute_presence: AttributePresence` field to `PublishConfig` (default `'values-only'`, alias `'attribute-presence'`).
3. Add `attribute_presence: AttributePresence | None` field to `TableSection` only (default `None`, alias `'attribute-presence'`, meaning "use global").
4. Extract condition evaluation from `analyse.py` into a shared helper in `metamodel.py`. Define `evaluate_condition(artifact_fields, atype, condition, metamodel) -> bool` and `is_attribute_mandatory(attr_name, atype, artifact, metamodel) -> bool` using this shared helper. Log a warning if mode is `mandatory` but metamodel is unavailable.
5. Modify the table rendering loop in `render_block` to apply the presence filter. Text sections remain unchanged (always skip empty values).

### Configuration Example (YAML)

```yaml
start_level: 1
attribute-presence: mandatory

render:
  REQ:
    - type: table
      attribute-presence: values-only
      attributes:
        - id:
            alias: "Identifier"
        - parent:
            alias: "Parent"
        - safety:
            alias: "Safety"
    - type: text
      mode: block
      attributes:
        - contents:
            alias: "Requirement"
```

### Configuration Example (TOML)

```toml
start_level = 1
attribute-presence = "mandatory"

[[render.REQ]]
type = "table"
attribute-presence = "values-only"

[[render.REQ.attributes]]
[render.REQ.attributes.id]
alias = "Identifier"

[[render.REQ.attributes]]
[render.REQ.attributes.parent]
alias = "Parent"

[[render.REQ.attributes]]
[render.REQ.attributes.safety]
alias = "Safety"

[[render.REQ]]
type = "text"
mode = "block"

[[render.REQ.attributes]]
[render.REQ.attributes.contents]
alias = "Requirement"
```

### Rendered Output Examples

Given an artifact `REQ-1` with fields `{id: "REQ-1", contents: "The system shall...", safety: "yes"}` (no `parent` value), and metamodel where `parent` is mandatory and `safety` is mandatory:

**With `attribute_presence: all`** (table section):
```markdown
|           |       |
|-----------|-------|
| Identifier | REQ-1 |
| Parent | |
| Safety | yes |
```

**With `attribute_presence: mandatory`** (table section, assuming `parent` is conditional mandatory `if not derive` and `derive` is absent/false for this artifact):
```markdown
|           |       |
|-----------|-------|
| Identifier | REQ-1 |
| Parent | |
| Safety | yes |
```

**With `attribute_presence: values-only`** (table section):
```markdown
|           |       |
|-----------|-------|
| Identifier | REQ-1 |
| Safety | yes |
```

### Condition Evaluation Logic

For `mandatory` mode, to determine if an attribute is mandatory for a given artifact:

```python
def is_attribute_mandatory(attr_name: str, atype: str, artifact: Artifact, metamodel: dict | None) -> bool:
    if not metamodel:
        return False
    atype_def = metamodel.get('artifacts', {}).get(atype)
    if not atype_def:
        return False
    rules = atype_def.get('attributes', {}).get(attr_name, [])
    for rule in rules:
        if rule.get('presence') != 'mandatory':
            continue
        condition = rule.get('condition')
        if condition is None:
            return True  # unconditionally mandatory
        # Evaluate condition
        anchor = condition['anchor']
        negated = condition['negated']
        anchor_value = artifact.fields.get(anchor)
        anchor_truthy = _is_truthy(anchor_value, anchor, atype, metamodel)
        if negated:
            # "if not X" → mandatory when X is falsy
            if not anchor_truthy:
                return True
        else:
            # "if X" → mandatory when X is truthy
            if anchor_truthy:
                return True
    return False
```

Truthiness evaluation for anchor fields:
- `None` (missing) → falsy
- Empty string → falsy
- Boolean string values: resolved via metamodel's custom boolean definitions (e.g., `"yes"` → truthy, `"no"` → falsy)
- Any other non-empty string → truthy
- List: truthy if non-empty

### Resolution Order

1. If the `TableSection` has an explicit `attribute_presence` value, use it.
2. Otherwise, use the global `attribute_presence` from `PublishConfig`.

### Filtering Logic in Render

For each attribute in a section's `attributes` list:

```python
def should_render_attribute(attr_name, val, presence_mode, atype, artifact, metamodel):
    if val:  # has a value
        return True
    if presence_mode == 'values-only':
        return False
    if presence_mode == 'all':
        return True
    # presence_mode == 'mandatory'
    return is_attribute_mandatory(attr_name, atype, artifact, metamodel)
```

For **table sections**: when `should_render_attribute` is True but value is None/empty, render `| Alias | |`.

For **text sections**: when value is None/empty, always skip (regardless of mode). Text rendering with an empty value produces no useful output.

## Task Breakdown

### Task 1: Add `attribute_presence` field to Pydantic models

**Objective:** Extend `PublishConfig` and `TableSection` with the new setting.

**Implementation guidance:**
- In `src/syntagmax/publish_config.py`:
  - Define `AttributePresence = Literal['all', 'mandatory', 'values-only']` at module level.
  - Add `attribute_presence: AttributePresence = Field(default='values-only', alias='attribute-presence')` to `PublishConfig`.
  - Add `attribute_presence: AttributePresence | None = Field(default=None, alias='attribute-presence')` to `TableSection`.
  - Do NOT add `attribute_presence` to `TextSection` (it has no effect and `extra='forbid'` would reject invalid fields anyway).

**Test requirements:**
- Unit test: `PublishConfig()` has `attribute_presence == 'values-only'`.
- Unit test: `PublishConfig.model_validate({'attribute-presence': 'mandatory'})` parses correctly via alias.
- Unit test: `PublishConfig.model_validate({'attribute_presence': 'mandatory'})` parses correctly via field name (populate_by_name=True).
- Unit test: `PublishConfig.model_validate({'attribute-presence': 'invalid'})` raises `ValidationError`.
- Unit test: `TableSection` with `attribute-presence: 'all'` parses correctly.
- Unit test: `TableSection` without `attribute-presence` has `None`.

**Demo:** `PublishConfig.model_validate({'attribute-presence': 'mandatory'}).attribute_presence == 'mandatory'`

### Task 2: Implement metamodel condition evaluator as shared helper

**Objective:** Extract condition evaluation logic from `analyse.py` into `metamodel.py` as a shared helper, and create `is_attribute_mandatory` for use in publishing.

**Implementation guidance:**
- In `src/syntagmax/metamodel.py`, add:
  - `evaluate_condition(artifact_fields: dict, atype: str, condition: dict | None, metamodel: dict) -> bool` — shared implementation of condition evaluation extracted from `ArtifactValidator._evaluate_condition`.
  - `is_attribute_mandatory(attr_name: str, atype: str, artifact_fields: dict, metamodel: dict | None) -> bool` — iterates rules, evaluates conditions, returns True if any mandatory rule applies.
- Refactor `ArtifactValidator._evaluate_condition` in `analyse.py` to call the shared helper.
- For truthiness evaluation (inside `evaluate_condition`):
  - If value is `None` or empty string → `False`.
  - If value is a list → truthy if non-empty.
  - Look up the anchor attribute's rules in the metamodel to find custom boolean values. If the value matches a `true` keyword → `True`; if it matches a `false` keyword → `False`.
  - Otherwise, any non-empty string → `True`.

**Test requirements:**
- Unit test: unconditional mandatory attribute → `True`.
- Unit test: optional attribute → `False`.
- Unit test: conditional `mandatory if not derive` where `derive` is absent → `True` (condition holds).
- Unit test: conditional `mandatory if not derive` where `derive` is `"yes"` (truthy) → `False` (condition doesn't hold).
- Unit test: conditional `mandatory if derive` where `derive` is `"yes"` → `True`.
- Unit test: no metamodel → `False`.
- Unit test: atype not in metamodel → `False`.
- Unit test: attribute not in metamodel → `False`.
- Unit test: `ArtifactValidator` still passes existing tests after refactoring.

**Demo:** `is_attribute_mandatory('parent', 'SRS', artifact_fields_with_derive_false, metamodel)` returns `True`.

### Task 3: Implement presence filtering in table section rendering

**Objective:** Modify the `TableSection` rendering loop in `render_block` to apply the attribute presence filter.

**Implementation guidance:**
- In `publish.py`, in the `isinstance(sec, TableSection)` branch of `render_block`:
  - Resolve effective presence: `sec.attribute_presence if sec.attribute_presence is not None else pub_config.attribute_presence`.
  - Resolve metamodel via `context.config.metamodel` if context is available.
  - If effective presence is `mandatory` and metamodel is unavailable, log a warning and degrade to `values-only`.
  - For each attribute in `sec.attributes`:
    - Get the value via `get_artifact_field_value`.
    - Apply `should_render_attribute(attr_name, val, presence_mode, atype, artifact_fields, metamodel)`.
    - If should render: append row with `val or ''` (empty cell for None).
    - If should not render: skip.
- The existing `if rows:` check for spacer and table header remains — only emit table when at least one row passes the filter.

**Test requirements:**
- Unit test: `all` mode — attribute without value appears as empty cell in table.
- Unit test: `mandatory` mode — mandatory attribute without value appears; optional without value is skipped.
- Unit test: `values-only` mode — only attributes with values rendered (current behavior preserved).
- Unit test: per-section override takes precedence over global.
- Unit test: conditional mandatory attribute appears/disappears based on artifact's anchor field value.
- Unit test: no context (metamodel unavailable) with `mandatory` mode degrades to `values-only` and logs a warning.

**Demo:** Rendering an artifact with `attribute_presence: all` in a table section shows all listed attributes, including those without values.

### Task 4: Verify text section rendering remains unchanged

**Objective:** Confirm that text sections always skip empty-value attributes regardless of the global `attribute_presence` mode.

**Implementation guidance:**
- No code changes needed for text sections. The existing `if val:` check in the `TextSection` branch already provides `values-only` behavior.
- The `attribute_presence` field is NOT added to `TextSection`, so the global setting does not apply to text sections.
- Add a test to confirm this behavior is preserved.

**Test requirements:**
- Unit test: text section skips attributes without values (existing behavior confirmed).
- Unit test: text section with values renders normally.

**Demo:** Text sections behave identically regardless of the global `attribute_presence` setting.

### Task 5: Update documentation

**Objective:** Document the new `attribute_presence` setting in the publishing reference.

**Implementation guidance:**
- Update `docs/reference/publishing.md`:
  - Add `attribute-presence` to the Global Parameters table with type `string`, default `"values-only"`, and description.
  - In the Render Section documentation, document the per-section `attribute-presence` override on `table` section type only.
  - Add a note explaining that text sections always skip empty-value attributes and do not support this setting.
  - Add a note explaining that the fallback renderer is unaffected by this setting.
  - Update the Full Schema (YAML) and Full Schema (TOML) examples to include `attribute-presence`.
  - Add a subsection explaining condition evaluation for `mandatory` mode.

**Test requirements:** N/A (documentation only).

**Demo:** Documentation clearly describes global and per-section `attribute-presence` with examples and condition evaluation semantics.
