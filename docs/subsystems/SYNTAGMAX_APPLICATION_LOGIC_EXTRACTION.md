# Syntagmax Application Logic — Extraction Subsystem

> Covers input-driver dispatch, artifact construction, Markdown/Obsidian markers, frontmatter, text, sidecars, notebooks, simple Markdown, filters, and extraction errors. Source: `extract.py`, `artifact.py`, `extractors/`.

## 1. Dispatch and common output

`EXTRACTORS` maps:

```text
text → TextExtractor
sidecar → SidecarExtractor
obsidian → ObsidianExtractor
ipynb → IPynbExtractor
simple-markdown → SimpleMarkdownExtractor
```

For every configured input record:

1. Instantiate the driver with `Config`, `InputRecord`, and metamodel.
2. Extract artifacts/blocks.
3. Append artifacts to one global list.
4. Convert extractor errors into report extraction errors.

`build_artifact_map()` then rejects missing IDs and duplicate IDs. Extraction locations are relative to `Config.base_dir()`.

## 2. Common artifact construction

`ArtifactBuilder`:

- sets driver, record, and source location;
- requires one ID and atype;
- always adds `id` and driver-provided fields;
- stores `contents` as the body field;
- uses metamodel multiplicity to choose scalar/list storage;
- splits comma-separated multiple references/enums;
- rejects duplicate scalar fields;
- initializes missing multiple fields as empty lists.

`<undefined>` is used when a source lacks an ID; the map stage reports and excludes it.

## 3. Text driver

### Input syntax

The `text` driver scans files for sections delimited by `[<` and `>]`:

```text
[< ID=REQ-001 TYPE=REQ status=active >>> Requirement body >]
```

The grammar supports:

- ID directive;
- optional type directive;
- header attributes;
- body contents.

Rules:

- text before/between/after artifacts becomes `TextBlock`;
- missing ID logs a warning and creates an undefined-ID artifact block;
- absent type uses record `atype`;
- `id`, `contents`, and header attributes become artifact fields;
- parser/validation errors become `ErrorBlock` and warnings.
- unreadable/undecodable files are skipped.

ID renumbering replaces `ID=...`/`id=...` inside line ranges.

## 4. Markdown and Obsidian drivers

`MarkdownExtractor` is the base for `markdown`, `obsidian`, and `ipynb`.

### 4.1 Artifact detection

- Record `marker` selects the artifact start marker, case-insensitively.
- A segment ends at a closing `[/MARKER]`, a fenced YAML block end, or a context-aware fallback boundary.
- Fallback boundaries include next artifact marker, configured fragment marker, ATX heading, blank line, or EOF.
- Lark parses contents, inline `[FIELD]` blocks, and optional fenced YAML metadata.
- YAML must contain an `attrs` mapping when present.
- YAML attributes override inline attributes for ID/atype extraction.
- `id` and `atype` are consumed as identity/type fields rather than ordinary duplicate fields.
- Missing ID logs a warning and uses `<undefined>`.
- Configured record atype is used unless source metadata supplies `atype`.
- NBSP in a requirement is an error block.
- Parse and processing failures become `ErrorBlock`.

### 4.2 Field sources

- Inline field: `[status] active` and continuation lines.
- YAML field: fenced `yaml` block containing `attrs:`.
- Values are converted through extractor YAML conversion rules.
- Multiple fields are repeated/list-valued according to metamodel.
- Artifact contents are the unassigned body text.

### 4.3 Fragment markers

Configured Obsidian markers are applied to unmarked text in three passes:

1. closed pair: `[COM]body[/COM]`;
2. unclosed pair: `[COM]body` terminated by blank line, next marker, heading, or EOF;
3. line prefix: `[COM] body` terminated by blank line/EOF.

Optional marker IDs are accepted as `[COM id]`:

- valid characters: letters, digits, underscore, dot, hyphen;
- invalid IDs produce `ErrorBlock`;
- no ID leaves `TextBlock.id = None`, later assigned by publisher or marker editor;
- marker names are normalized uppercase.

### 4.4 Heading splitting

Unmarked text is split into `HEADING` blocks for ATX headings with up to three leading spaces and 1–6 `#` characters. Fenced-code content is protected. Heading blocks are later rendered as ordinary text headings by publishing.

### 4.5 Element filtering

Configured exclusions apply to `TextBlock`s, not artifact blocks. Fenced code is protected. Supported elements:

- `frontmatter`: whole initial block removal;
- `callouts`: strip prefix (`only`) or remove line;
- `headings`: strip `#` (`only`) or remove line;
- `horizontal_rules`: remove line;
- `tags`: strip tags, remove tagged lines, or remove only when tag starts line.

Inline code spans and fenced code tags are protected.

## 5. Obsidian-specific behavior

`ObsidianExtractor` applies the base Markdown extraction, then:

- if effective strict line breaks are OFF, transforms TextBlock content and artifact `contents` with hard-break conversion;
- strict transformation skips code fences, empty lines, block syntax, paragraph separators, and existing hard breaks;
- `auto` reads `strictLineBreaks` from configured `app.json`; unavailable settings warn and default to strict ON.

## 6. Simple Markdown driver

One file = one artifact.

1. Read UTF-8 with BOM support.
2. Parse initial YAML frontmatter delimited by `---`.
3. If no frontmatter, use empty attributes and entire file as body.
4. If YAML is malformed, return `ErrorBlock`.
5. Extract `id` case-insensitively; fallback is filename stem.
6. Extract `atype` case-insensitively; fallback is record default.
7. Remaining top-level frontmatter keys become fields.
8. Body, stripped, becomes `contents`.
9. Empty files produce no blocks.
10. Non-dictionary frontmatter is treated as absent with warning.

Editing uses round-trip YAML and preserves quotes/order/comments where possible. Inline fields are unsupported.

## 7. Sidecar driver

For each original file:

- skip `.stmx`/`.syntagmax` metadata files themselves;
- require exactly one sidecar: `<file>.stmx` or `<file>.syntagmax`;
- both sidecars → error block;
- neither → error block;
- malformed/non-dictionary YAML → error block;
- missing case-insensitive `id` → error block;
- `atype` defaults to record atype;
- source location includes original file plus sidecar.

A full extraction pass also scans for orphaned sidecars without matching originals and reports errors.

## 8. IPython notebook driver

- Parse notebook JSON; malformed JSON → error block.
- Iterate cells in order.
- Markdown cells containing the record artifact marker are parsed with Markdown logic.
- Location is `NotebookLocation(file, line range, cell index)`.
- Other cells become plain `TextBlock`s when source is nonempty.

## 9. Extraction invariants

- Driver names must match the dispatch registry.
- Driver errors are represented as blocks/report errors rather than silently changing source data.
- Artifact IDs are not globally guaranteed unique until map construction.
- Input file lists are supplied by configuration and are sorted by publisher/editor consumers where deterministic order is needed.
- **`UNVERIFIED`:** exact behavior for malformed Unicode in every driver and all fallback boundary corner cases requires the full extractor test matrix.
