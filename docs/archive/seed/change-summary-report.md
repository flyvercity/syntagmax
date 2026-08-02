# Change Summary Report Mode

GitHub Issue: #73

## Intent

Add a `--summary` flag to `syntagmax change report` that produces an abbreviated
Markdown report for quick review — showing *what* changed without the full content.

## Activation

```bash
syntagmax change report --summary --base <rev> --target <rev>
```

## Report Sections

The summary report contains only:

1. **Repository Information** — same as the full report header.
2. **Summary** — aggregate statistics (files changed, artefacts added/modified/removed).
3. **Changed Files** — per-file breakdown (see below).

Detailed change content (object text, attribute diffs, OLD/NEW blocks) is omitted.

## Per-File Breakdown

For each changed file display:

- File path (as heading)
- File status (Added / Modified / Removed)
- List of changed objects with their ID, type, and change status
- List of plain text fragment changes with line ranges

### Example

```text
## docs/system.md

Status: Modified

Objects

+ REQ-101 (Modified)
+ REQ-102 (Added)
+ REQ-110 (Removed)

Text fragments

* Modified (lines 45-52 → 45-56)
* Added (lines 128-135)
```

## Object Representation

Each object entry shows only:

- Identifier
- Object type
- Change status (Added / Modified / Removed)

No text content, attribute changes, or link changes.

## Text Fragment Representation

Each non-artefact block shows:

- Change type (Added / Modified / Removed)
- Line ranges in base and target versions

No fragment content included.

## Follow-up Tasks

- Amend README.md change reports section to document `--summary`.
- Update `docs/reference/` if a change-report reference page exists.
- Add example output to the documentation.
