# Syntagmax Application Logic — Editing Subsystem

> Covers artifact identification, bulk attribute editing, fragment-marker renumbering, dry-run rules, and source-file mutation. Source: `edit.py`, `edit_attrs.py`, `edit_markers.py`, extractor update methods.

## 1. Identification / ID renumbering

`renumber_artifacts(config, atype=None, dry_run=False, force=False)`:

1. Extract all artifacts; extraction errors abort with `False`.
2. Filter by atype when supplied.
3. Sort by source location for deterministic assignment.
4. Resolve schema per artifact:
   - current template ID containing `{num}`/`{atype}`;
   - metamodel ID schema;
   - fallback `{atype}-{num:3}`.
5. Abort if any resolved schema has multiple `{num}` macros.
6. First pass records valid numeric IDs and maximum number per atype.
7. Ignore template, undefined, empty, and schema-without-number IDs for numbering.
8. Second pass:
   - normal mode starts each atype at max+1;
   - force mode starts each atype at 1.
9. Preserve valid IDs in normal mode.
10. Renumber undefined, empty, template, or schema-mismatching IDs.
11. In dry-run, log planned changes only.
12. Otherwise group updates by file and call the driver’s `update_artifacts()`.
13. Log preserved/changed/total counts; duplicate valid IDs produce a warning.

ID generation:

- replace `{atype}` with artifact type;
- replace `{num}` with number;
- replace `{num:N}` with minimum zero-padding;
- never truncate numbers wider than padding.

Driver update behavior:

- Markdown/Obsidian: round-trip YAML ID when present, then update inline `[id]` fallback.
- Simple Markdown: round-trip frontmatter and insert/update case-insensitive `id`.
- Text: replace `ID=...` or `id=...` within artifact line range.
- Unsupported driver update logs a warning.

## 2. Bulk attribute editing

`manipulate_attributes()` targets one configured input record.

Preconditions:

- named section must exist;
- driver must be `obsidian`;
- metamodel-driven add requires a metamodel;
- operation is `add`, `del`, or `replace`;
- target is YAML `attr` or inline `field`.

Attribute selection:

- explicit `--name` targets one attribute;
- add without name selects all mandatory metamodel attributes except `contents`;
- metamodel-driven add uses `TBD`;
- add without value/CSV also uses `TBD`;
- unknown explicit attributes produce a warning but are still added.

CSV values:

- UTF-8 BOM is supported;
- required ID/value columns must exist;
- duplicate IDs use the last value with warning;
- missing mapping uses literal fallback if supplied, otherwise skips artifact;
- malformed/encoding/column errors are fatal.

Computation:

1. Extract target section artifacts.
2. Group by source file.
3. Resolve each value.
4. For `add`, skip artifacts already containing the target attribute.
5. In dry-run, print planned changes and do not write.
6. Otherwise call extractor update method per file, then write returned content.
7. Any write error is fatal.
8. Print modified/skipped/unmatched summary.

YAML attribute updates preserve ordering/comments through round-trip YAML when possible. Inline field updates insert before the closing artifact marker/YAML block or append at end. Simple Markdown supports YAML frontmatter only; inline fields are unsupported.

## 3. Fragment-marker renumbering

`renumber_markers(config, section=None, marker_filter=None, dry_run=False)`:

1. Select configured Obsidian records with markers.
2. Optional section restricts to one record.
3. Optional marker filter is normalized uppercase and must exist in a selected record.
4. Extract files in deterministic relative-path order.
5. Collect existing numeric IDs per marker.
6. Collect unmarked `TextBlock`s with source offsets.
7. For each marker type, next ID = max(existing numeric IDs) + 1, or `1` when none exist.
8. Assign IDs in extraction/file order.
9. Compute opening-tag replacements from source offsets.
10. Apply replacements bottom-to-top to preserve offsets.
11. Dry-run prints assignments but does not write.
12. Non-dry-run preserves CRLF and writes each modified file once.
13. Print assignment summary.

Only configured user markers are changed; internal/heading markers are ignored. Existing nonnumeric explicit IDs are not included in the numeric maximum.

## 4. Mutation safety rules

- Dry-run is implemented independently per command.
- Updates are grouped and applied in reverse source order where offsets/line ranges are used.
- Attribute edits use temporary in-memory content per file before writing.
- Identification/marker commands can modify source files and do not create a Git commit.
- **`UNVERIFIED`:** exact CLI exit code for early validation returns in `edit attrs` and `edit markers renumber`; handlers print and return without explicit `SystemExit`.
