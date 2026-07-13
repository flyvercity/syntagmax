# Spec: Table Spacer Option for Publishing

## Problem Statement

Tables in published output lack configurable visual spacing before them. When multiple sections are rendered sequentially (e.g., a text block followed by a table), the table appears immediately after the previous content. Users need control over the number of visible blank lines prepended before tables to improve readability in rendered Markdown and DOCX output.

## Requirements

1. Add a global `table_spacer` setting in the publish config (default: `1`, must be an integer between 0 and 20, supports kebab-case `table-spacer`)
2. Add a per-section `spacer` field on `TableSection` (optional, overrides the global, must be an integer between 0 and 20)
3. Spacer produces ASCII `&nbsp;` paragraph lines before the table (each unit = one visible blank line). The literal unicode `\xa0` character must not be used to avoid parser validation issues.
4. Applies to both custom `TableSection` rendering and fallback metadata table
5. `spacer: 0` means no spacer lines prepended

## Background

- `TableSection` is a Pydantic model in `publish_config.py` with `type` and `attributes` fields
- `PublishConfig` holds global settings like `start_level`, `include_plain_text`, etc.
- Table rendering happens in `publish.py` at two locations:
  - Custom `TableSection` rendering (in the `isinstance(sec, TableSection)` branch of `render_block`)
  - Fallback `render_artifact_fallback` function
- The final output in `render_block_tree` collapses 3+ consecutive newlines into 2 (`re.sub(r'\n{3,}', '\n\n', result)`), so plain newlines cannot produce multiple visible blank lines
- Using `&nbsp;\n\n` paragraphs as spacers survives the collapse and produces visible blank lines in both Markdown renderers and Pandoc DOCX/PDF export
- **Important:** The markdown extractor in `src/syntagmax/extractors/markdown.py` detects and flags literal unicode non-breaking spaces (`\xa0`) as validation errors. The publisher must use the ASCII entity `&nbsp;` exclusively — never the literal unicode character `\xa0` — to ensure published output files do not trigger extraction errors if read back as input.

## Proposed Solution

Add a global `table_spacer` integer field to `PublishConfig` with a default of `1`. Add an optional `spacer` integer field to `TableSection` that overrides the global when set. During rendering, resolve the effective spacer (per-section if set, else global) and prepend `'&nbsp;\n\n' * effective_spacer` before the table header row when the table has rows to render.

### Configuration Example (YAML)

```yaml
start_level: 1
table_spacer: 2

render:
  REQ:
    - type: table
      spacer: 3
      attributes:
        - id:
            alias: "ID"
        - parent:
            alias: "Parent"
    - type: text
      mode: block
      attributes:
        - contents:
            alias: "Requirement"
```

### Configuration Example (TOML)

```toml
start_level = 1
table_spacer = 2

[[render.REQ]]
type = "table"
spacer = 3

[[render.REQ.attributes]]
[render.REQ.attributes.id]
alias = "ID"

[[render.REQ.attributes]]
[render.REQ.attributes.parent]
alias = "Parent"

[[render.REQ]]
type = "text"
mode = "block"

[[render.REQ.attributes]]
[render.REQ.attributes.contents]
alias = "Requirement"
```

### Rendered Output Example

With `spacer: 2`, the table output becomes:

```markdown
&nbsp;

&nbsp;

|           |       |
|-----------|-------|
| ID | REQ-1 |
| Parent | SYS-1 |
```

Each `&nbsp;` paragraph acts as a visible blank line in rendered output.

### Resolution Order

1. If the `TableSection` has an explicit `spacer` value, use it.
2. Otherwise, use the global `table_spacer` from `PublishConfig`.

## Task Breakdown

### Task 1: Add `spacer` field to `TableSection` model

**Objective:** Extend the `TableSection` Pydantic model with an optional `spacer` integer field.

**Implementation guidance:**
- Add `spacer: int | None = Field(default=None, ge=0, le=20)` to `TableSection` in `publish_config.py`
- The field is optional; `None` means "use global `table_spacer`"

**Test requirements:**
- Unit test: `TableSection` validates with `spacer` present (integer values)
- Unit test: `TableSection` validates without `spacer` (defaults to `None`)
- Unit test: `TableSection` rejects non-integer `spacer` values
- Unit test: `TableSection` rejects negative spacer values (e.g. `-1`)
- Unit test: `TableSection` rejects spacer values greater than 20 (e.g. `21`)

**Demo:** `TableSection.model_validate({'type': 'table', 'spacer': 2, 'attributes': [{'id': {'alias': 'ID'}}]})` succeeds with `spacer == 2`.

### Task 2: Add `table_spacer` global field to `PublishConfig` model

**Objective:** Add a global `table_spacer` setting with default of `1`.

**Implementation guidance:**
- Add `table_spacer: int = Field(default=1, alias='table-spacer', ge=0, le=20)` to `PublishConfig` in `publish_config.py`

**Test requirements:**
- Unit test: `PublishConfig()` has `table_spacer == 1`
- Unit test: YAML with `table_spacer: 3` parses correctly
- Unit test: TOML with `table_spacer = 3` parses correctly
- Unit test: YAML with kebab-case `table-spacer: 3` parses correctly
- Unit test: non-integer values are rejected
- Unit test: `PublishConfig` rejects negative values and values greater than 20

**Demo:** `PublishConfig.model_validate({'table_spacer': 2}).table_spacer == 2`

### Task 3: Update custom `TableSection` rendering to prepend spacer lines

**Objective:** Modify the table rendering in `render_block` to emit `&nbsp;\n\n` lines before the table.

**Implementation guidance:**
- In `publish.py`, in the `isinstance(sec, TableSection)` branch, resolve effective spacer: `sec.spacer if sec.spacer is not None else pub_config.table_spacer`
- Before appending the table header row (`|---|---|`), prepend `'&nbsp;\n\n' * effective_spacer`
- Only emit spacer when the table has rows to render (i.e., when `rows` is non-empty)

**Test requirements:**
- Unit test: `render_block` with per-section `spacer: 2` produces two `&nbsp;` paragraphs before the table
- Unit test: `render_block` with `spacer: 0` produces no spacer
- Unit test: `render_block` with no per-section spacer uses global `table_spacer`
- Unit test: empty table (no matching attributes) produces no spacer

**Demo:** Rendered artifact block with table section shows `&nbsp;` lines before the table.

### Task 4: Update fallback table rendering to prepend spacer lines

**Objective:** Modify `render_artifact_fallback` to use the global `table_spacer` setting.

**Implementation guidance:**
- Change `render_artifact_fallback` signature to accept `table_spacer: int` parameter (or pass `pub_config`)
- Before emitting the fallback metadata table header, prepend `'&nbsp;\n\n' * table_spacer`
- Only emit spacer when the table has fields to render (i.e., when `fields` dict is non-empty)
- Update all call sites of `render_artifact_fallback` to pass the spacer value

**Test requirements:**
- Unit test: fallback rendering with `table_spacer: 2` produces two `&nbsp;` paragraphs before the metadata table
- Unit test: fallback rendering with `table_spacer: 0` produces no spacer
- Unit test: fallback rendering with default (`table_spacer: 1`) produces one `&nbsp;` paragraph

**Demo:** Artifact rendered without custom config shows configurable spacing before its metadata table.

### Task 5: Update documentation

**Objective:** Document the new `table_spacer` global and per-section `spacer` options.

**Implementation guidance:**
- Update `docs/reference/publishing.md`:
  - Add `table_spacer` to the Global Parameters table
  - Document `spacer` in the Render Section's table type description
  - Add examples in both YAML and TOML full schema sections
- Update `README.md` if appropriate

**Test requirements:** N/A (documentation).

**Demo:** Published docs show the new options with examples.
