# Brainstorm: Improve Analyze Report Structure and UX

**Issue**: [#122](https://github.com/flyvercity/syntagmax/issues/122)

## Problem Summary

The current analyze report is a flat list of numbered errors followed by flat metrics/impact sections. With 150+ errors, it's difficult to:
1. Understand which **input source** has problems
2. Identify **categories** of errors (schema violations, missing refs, duplicate IDs, etc.)
3. Navigate to the **source file** where the error lives

## Current State

- **Report structure**: `# Analysis Report → ## Errors (flat numbered list) → ## Metrics → ## Impact`
- **Error format**: plain strings like `"Attribute 'parent' value 'X' refers to an unknown artifact ID 'X' (ATYPE.AID.path/to/file:78-102@none)"`
- **No grouping** by input record or error category
- **No file links** — the location is embedded in the error text parenthetically
- **Report data model** (`report.py`): `errors: list[str]` — just strings, no structured metadata

## Proposed Solutions

### 1. Structured Error Objects (replacing `list[str]`)

Replace `errors: list[str]` with `errors: list[ReportError]` where:

```python
@dataclass
class ReportError:
    message: str
    category: str          # e.g. "schema", "reference", "trace", "duplicate", "extraction"
    input_record: str | None  # e.g. "software-requirements"
    artifact_id: str | None
    artifact_type: str | None
    file_path: str | None
    line_range: tuple[int, int] | None
```

**Categories** (inferred from error message patterns or set at generation site):
- `schema` — ID doesn't match schema
- `attribute` — missing/invalid/extra attributes
- `reference` — unknown artifact references
- `trace` — missing mandatory traces, forbidden traces
- `duplicate` — duplicate artifact IDs
- `extraction` — driver-level extraction failures
- `structure` — tree structure issues (no root, etc.)

**Approach**: Modify `analyse_tree`, `build_artifact_map`, `extract`, etc. to append `ReportError` objects instead of strings. Each site already has the artifact/location context.

### 2. Report Template Restructuring

Proposed new report hierarchy:

```
# Analysis Report

## Errors
Total errors: 151

### system-requirements (45 errors)
#### Attribute Errors (30)
- ...
#### Reference Errors (15)
- ...

### software-requirements (106 errors)
#### Schema Errors (20)
- ...
#### Trace Errors (86)
- ...

## Artifact Tree
...

## Metrics
### system-requirements
...
### software-requirements
...

## Impact Analysis
### system-requirements
...
### software-requirements
...
```

**Key changes**:
- Group errors by input record name, then by category
- Group metrics by input record (when meaningful)
- Impact can remain flat (it's already about cross-record links)

### 3. File Links in Error Messages

Two link styles configurable via `config.toml`:

```toml
[report]
path_as_links = true
wiki_links = false     # true = [[path/to/file]], false = [file](path/to/file)
```

Error rendering becomes:
- **Wiki links (Obsidian)**: `Attribute 'parent' refers to unknown ID (REQ-059 in [[path/to/file]])`
- **Markdown links**: `Attribute 'parent' refers to unknown ID (REQ-059 in [file.md](path/to/file.md#L78))`
- **No links** (default/off): current behaviour, plain path text

**Line anchors**: Use `#L78` for standard Markdown viewers (GitHub-compatible), or omit for wiki links (Obsidian doesn't support line anchors in wikilinks).

### 4. Configuration Shape

```toml
[report]
path_as_links = true       # default: false (backward compat)
wiki_links = false          # default: false; only relevant when path_as_links = true
```

CLI override possible:
```bash
syntagmax --report-links --report-wiki-links analyze
```

### 5. Implementation Considerations

**Backward compatibility**:
- The `ReportError` needs a `__str__` method that produces the current plain-text format for MCP, logging, and the `--warnings-as-errors` handler.
- The template must still render correctly for users who don't set `[report]` options.

**Grouping logic**:
- Errors from `build_artifact_map` (duplicate IDs) — can be mapped to an input record via `artifact.record.name`
- Errors from `analyse_tree` — the artifact has `.record`
- Errors from `extract` — already per-record in the extraction loop
- Some errors are "global" (e.g., "must have exactly one root") — put under a special "Global" heading

**Metrics per input**:
- Currently metrics only report on a single `requirement_type`. Could break down by input record if multiple records have the same atype. This is a stretch goal — the primary ask is about errors.

**Impact per input**:
- Each suspicious link's artifact has a `.record`, so grouping is straightforward.

### 6. Stretch Ideas (not in scope for v1)

- **Collapsible sections** using `<details>` HTML for large error groups
- **Severity levels** (error vs warning) with distinct rendering
- **Error counts summary table** at the top (matrix: input × category)
- **JSON report output** option for CI integration

## Recommended Approach

1. **Phase 1**: Introduce `ReportError` dataclass, update all error-producing sites, update the Jinja2 template to group by input→category. Add `[report]` config section.
2. **Phase 2**: Implement `path_as_links` and `wiki_links` rendering in the template.
3. **Phase 3**: Group metrics and impact sections by input record.

**Risks**:
- Changing `errors: list[str]` to structured objects touches many modules (analyse, extract, tree, impact)
- Need to ensure all error sites consistently provide record/location metadata
- i18n: error categories need localisation support

## Open Questions

### Q1: Should the `[report]` section live in the project config or be a separate report config file?

**Answer**: _TBD_

### Q2: Should errors without a known input record (e.g. "must have exactly one root") go under a "Global" heading or remain at the top level?

**Answer**: _TBD_

### Q3: For wiki links, should the path be relative to the vault root or to the config file base directory?

**Answer**: _TBD_

### Q4: Should metrics be grouped by input record, or remain a single flat section (since they currently only target one `requirement_type`)?

**Answer**: _TBD_

### Q5: Should impact analysis results also be grouped by input record, or kept flat since they represent cross-record relationships?

**Answer**: _TBD_

### Q6: Is replacing `list[str]` with `list[ReportError]` acceptable as a breaking internal change, or do we need a migration period with dual support?

**Answer**: _TBD_

### Q7: Should the error category names be localised in the report, or kept as English technical identifiers?

**Answer**: _TBD_
