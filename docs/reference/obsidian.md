# Obsidian Driver Reference

The Obsidian driver extracts artifacts and text blocks from Markdown files authored in [Obsidian](https://obsidian.md). It is the primary driver for requirements management in Syntagmax and supports rich inline metadata, YAML attribute blocks, fragment markers, and flexible block termination.

> **Note:** Despite its name, the Obsidian driver works with any Markdown files organised into a directory tree. An Obsidian vault is not required — the driver simply processes `.md` files using the artifact syntax described below. Obsidian-specific features (vault integration, attachment path resolution) are optional and only activate when explicitly configured.

## Overview

Each Markdown file processed by the Obsidian driver produces a sequence of **blocks**:

- **ArtifactBlock** — a requirement or other tracked artifact with an ID, type, fields, and optional YAML metadata.
- **TextBlock** — surrounding prose, optionally tagged with a fragment marker (e.g., `COM`, `NOTE`).
- **ErrorBlock** — a parsing failure captured for reporting.

The driver scans for artifact start markers (`[MARKER]`) in the document, extracts the artifact segment, and parses it using a formal grammar. Everything between artifacts is captured as text blocks, which may be further split by fragment markers.

---

## Artifact Block Structure

An artifact block begins with a start marker and contains body text, inline fields, and an optional terminator.

### Anatomy

````markdown
[REQ]
The system shall implement feature X with performance constraint Y.
[id] REQ-042
[parent] SYS-007
```yaml
attrs:
  title: Feature X Implementation
  status: active
  priority: high
  verify: "Integration test: test_feature_x"
```
````

The block consists of:

1. **Start marker** — `[MARKER]` where MARKER matches the configured artifact marker (case-insensitive).
2. **Contents** — free-form text lines describing the artifact. Any line that does not start with `[`, `` ```yaml ``, or `[/` is treated as content.
3. **Inline fields** — lines starting with `[field_name]` followed by a value. Fields can span multiple lines (continuation lines must not start with `[`, `` ```yaml ``, or `[/`).
4. **Terminator** — one of: a YAML block, an explicit closing tag `[/MARKER]`, or an implicit boundary (see [Block Termination Rules](#block-termination-rules)).

### Inline Fields

Fields are metadata key-value pairs embedded directly in the artifact body:

```markdown
[id] REQ-001
[parent] SYS-001
[justification] This is required because
  of regulatory mandate XYZ.
```

- Field names are case-insensitive and stored lowercase.
- The special fields `id` and `atype` have semantic meaning (artifact identity and type override).
- Multi-line field values are supported via continuation lines.

### YAML Metadata Block

An optional fenced YAML block provides structured attributes:

````markdown
```yaml
attrs:
  title: My Requirement
  status: active
  priority: high
  tag:
    - performance
    - safety
  derived: false
```
````

- The YAML block must contain an `attrs:` top-level key. If it is missing, the block is treated as a parse error.
- YAML attributes are merged with inline fields; YAML takes precedence for duplicate keys.
- The `id` attribute can appear in YAML instead of as an inline `[id]` field.
- Lists in YAML (e.g., `tag`) produce multiple field values for the same attribute.

### Minimal Artifact

The simplest valid artifact requires only a start marker and an `id`:

```markdown
[REQ]
The system shall do X.
[id] REQ-001
```

No YAML block or closing tag is needed — the block terminates at the next boundary (empty line, heading, EOF, etc.).

---

## Block Termination Rules

Artifact blocks are terminated by one of the following, checked in priority order:

| Priority | Terminator | Behaviour |
|----------|-----------|----------|
| 1 | **YAML block** (`` ```yaml `` … `` ``` ``) | Always wins. The segment extends through the closing `` ``` ``. |
| 2 | **Explicit closing tag** (`[/MARKER]`) | Traditional terminator. The segment extends through `[/MARKER]`. |
| 3 | **Another artifact start marker** | A new `[MARKER]` for the same configured marker starts a new block. The current block's search boundary is limited to the text before the next `[MARKER]`. |
| 4 | **Fragment marker at BOL** | A configured fragment marker (e.g., `[COM]`, `[NOTE]`) at the beginning of a line. |
| 5 | **Markdown heading at BOL** | A line starting with `# `, `## `, …, `###### ` (1–6 `#` followed by a space). |
| 6 | **Empty line** | One or more blank lines (LF or CRLF). |
| 7 | **End of file** | Implicit termination at document end. |

### Context-Aware Termination

Terminators 4–7 are **context-aware fallbacks**: they only apply when no YAML block (priority 1) or explicit closing tag (priority 2) is found for the current artifact before the next artifact start marker.

This means:

- **With `[/REQ]` or YAML present** — empty lines, headings, and fragment markers inside the block are allowed and do NOT terminate it. Multi-paragraph requirements work as expected.
- **Without `[/REQ]` or YAML** — the block terminates at the first fallback boundary encountered.

### Examples

**YAML terminator (priority 1):**

````markdown
[REQ]
Multi-paragraph requirement.

Second paragraph with details.
[id] REQ-001

```yaml
attrs:
  status: active
```

Text after — this is NOT part of the artifact.
````

The empty lines do NOT terminate because a YAML block exists.

**Explicit closing tag (priority 2):**
```markdown
[REQ]
First paragraph.

Second paragraph.
[id] REQ-001
[/REQ]

Text after.
```
The empty line does NOT terminate because `[/REQ]` exists.

**Empty line termination (priority 6):**
```markdown
[REQ]
The system shall do X.
[id] REQ-001

This text is NOT part of the artifact.
```
No YAML or `[/REQ]` exists, so the empty line terminates the block.

**Heading termination (priority 5):**
```markdown
[REQ]
The system shall do X.
[id] REQ-001
## Design Notes

This section is outside the artifact.
```
No YAML or `[/REQ]` exists, so the heading terminates the block.

**EOF termination (priority 7):**
```markdown
[REQ]
The system shall do X.
[id] REQ-001
```
No terminator at all — the block extends to end of file.

### What Does NOT Terminate

- **Obsidian tags** (`#tag-name` without a space after `#`) — these are NOT Markdown headings and do NOT terminate blocks.
- **`#` inside a line** (e.g., "C# compatible") — only `#` at the beginning of a line counts.
- **Fragment markers inside content** (e.g., "See [COM] for details") — only markers at the beginning of a line count as terminators.

### Empty Line Consumption

When an empty line terminates a block, all consecutive blank lines are consumed and do not appear in the subsequent text block. The next text block starts at the first non-whitespace line.

---

## Fragment Markers

Fragment markers tag non-artifact text with named labels for use in publication filtering.

### Configuration

```toml
[[input]]
name = "system-requirements"
dir = "SYS"
driver = "obsidian"
markers = ["COM", "NOTE"]
```

### Marker Formats

The Obsidian driver supports three fragment marker formats, applied as a pipeline:

#### 1. Closed Paired Markers

```markdown
[COM]This is a comment.[/COM]
[COM com-1]This is an identified comment.[/COM]
```

Traditional paired syntax. The marker is explicitly closed with `[/MARKER]`. Content between the markers can span multiple lines and include empty lines. An optional ID can be placed after the marker name.

#### 2. Unclosed Paired Markers

```markdown
[COM]This comment ends at the next blank line.

[COM intro]This identified comment also ends at the blank line.

Text after the comment.
```

When no `[/MARKER]` closing tag is present, the marked block terminates at:
- A double newline (empty line)
- The start of another fragment marker
- A Markdown heading
- End of string

#### 3. Line-Prefix Markers

```markdown
[COM] This is a single-paragraph comment that
terminates at the next blank line or end of file.

[COM section.1] This identified comment uses a line-prefix marker.

Next paragraph is unmarked.
```

A marker at the start of a line followed by a space and content. The block terminates at the next double newline or end of string. An optional ID can be placed after the marker name: `[COM my-id] content`.

### Processing Pipeline

The three formats are applied as sequential passes:

1. **Pass 1** — Extract all closed paired blocks (`[MARKER]...[/MARKER]`).
2. **Pass 2** — On remaining unmarked text, extract unclosed paired blocks.
3. **Pass 3** — On remaining unmarked text, extract line-prefix blocks.

This pipeline ensures that closed markers always take priority, and mixed styles within the same document work correctly.

### Validation Rules

- Marker names must match `^[a-zA-Z0-9_-]+$`
- Markers are case-insensitive (stored uppercase)
- No duplicates (case-insensitive) in the marker list
- Fragment markers must NOT collide with the artifact marker (e.g., `markers = ["REQ"]` when `marker = "REQ"` is a fatal error)
- Fragment markers must NOT collide with metamodel attribute names for the artifact type (e.g., `markers = ["status"]` when the metamodel defines `attribute status` is a fatal error)

### Block IDs

Fragment markers can carry an optional identifier for cross-referencing:

```markdown
[COM com-1]This is an identified commentary block.[/COM]
[NOTE intro]This note has an explicit ID.
```

#### ID Rules

- IDs must match `[a-zA-Z0-9_-.]` (letters, digits, underscore, hyphen, dot)
- IDs are optional — if absent, Syntagmax generates a deterministic short hash internally
- User-provided IDs must be unique within a given marker type across the entire project
- Duplicate explicit IDs produce extraction errors
- Auto-generated IDs (for blocks without explicit IDs) are not checked for uniqueness
- Invalid ID characters produce extraction errors

---

## ID and Type Resolution

Every artifact must have an `id`. The ID can come from:

1. An inline field: `[id] REQ-001`
2. A YAML attribute: `id: REQ-001` under `attrs:`

If both are present, the YAML value takes precedence. If neither is present, the artifact receives an undefined placeholder ID and a warning is logged.

The artifact type (`atype`) defaults to the input record's `atype` configuration value but can be overridden per-artifact with:

1. An inline field: `[atype] custom-type`
2. A YAML attribute: `atype: custom-type`

### Artifact Marker (`marker`)

By default, the driver uses the input record's `atype` value as the start/end marker (e.g., `atype = "REQ"` scans for `[REQ]` and `[/REQ]`). You can decouple marker text from the artifact type using the `marker` field:

```toml
[[input]]
name = "software-requirements"
dir = "REQ"
driver = "obsidian"
atype = "REQ"
marker = "SW"  # scans for [SW] / [/SW] instead of [REQ] / [/REQ]
```

This is useful when multiple input records share the same `atype` but use different marker labels in their source files.

---

## File Structure Conventions

A typical Obsidian requirement file:

````markdown
# REQ-001: Requirement Title

## Background

Context and rationale for this requirement. Links to related
system requirements: [[SYS-001]], [[SYS-002]].

## Requirement

[REQ]
The system shall implement the specified behaviour under
all operational conditions.
[id] REQ-001
[parent] SYS-001
```yaml
attrs:
  title: Requirement Title
  status: active
  priority: high
  verify: "test_requirement_001"
  derived: false
```
````

Key observations:
- The Markdown structure (headings, sections) is for human readability in Obsidian.
- Only the `[REQ]…` block is parsed as an artifact — surrounding Markdown is captured as text blocks.
- Obsidian wiki-links (`[[SYS-001]]`) in the prose are preserved as-is.

---

## Element Filtering

The Obsidian driver can exclude specific Markdown elements from extracted text blocks. This is configured via `exclude_elements` at the input record level or globally under `[drivers.obsidian]`.

| Element | Description |
|---------|-------------|
| `callouts` | Lines starting with `>` (blockquotes/callouts) |
| `headings` | Lines starting with `#` |
| `horizontal_rules` | Lines with three or more `-`, `*`, or `_` |
| `frontmatter` | YAML frontmatter at file start (`---` delimited) |
| `tags` | Inline Obsidian tags (`#tag`, `#nested/tag`) |

Filtering is code-block-aware: content inside fenced code blocks is never modified.

---

## Obsidian Vault Integration

When `[drivers.obsidian] integration = true`, Syntagmax reads the Obsidian vault's `app.json` to discover the configured `attachmentFolderPath`. This is used during publishing to resolve `![[image.png]]` references.

```toml
[drivers.obsidian]
integration = true
root = ".obsidian"  # optional, this is the default
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `integration` | No | `false` | Enable reading Obsidian vault settings. |
| `root` | No | `.obsidian` | Override path to the `.obsidian` directory (relative to base dir). |

### Path Resolution Rules

- **Vault-relative paths** (e.g., `"attachments/pics"`) — resolved relative to the project base directory.
- **Note-relative paths** (e.g., `"./attachments"` or `"."`) — resolved relative to the current source note's directory at publish time.

If `.obsidian/app.json` is missing, unreadable, or does not contain `attachmentFolderPath`, a warning is logged and publishing falls back to the standard vault-wide image scan.
