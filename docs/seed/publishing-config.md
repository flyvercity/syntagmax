# Specification: Publishing Module and Configuration System

This document specifies the requirements, workflows, and configuration model for the `publish` module of Syntagmax. The publishing module is responsible for assembling structured project sections into final deliverable documents (Markdown and DOCX).

## Overview & Objectives

The publishing system processes parsed project data, applies formatting templates, normalizes structures, and outputs clean documents for external consumption.

Key workflows:
- **Standard Publish**: Generates a single, structure-normalized Markdown document from a specified vault section.
- **DOCX Generation**: Converts the Markdown document to a Word document (.docx) using Pandoc (if available).
- **DOORS Mapping Mode**: Replaces requirement identifiers and custom attributes with values from an external CSV map to support legacy tooling import.

## Configuration Model

### Publishing Configuraion File Location

Publishing configuration is defined per input record as a YAML file, defaulting to `publish.yaml` in `.syntagmax` directory.

If not filename is given, and the file does not exist, assume all defaults.

#### Example

```toml
[[input]]
name = "system-requirements"
dir = "SYS"
driver = "obsidian"
atype = "SYS"
publish = "publish-sys-reqs.yaml
```

### Publishing Configuration

Specifies the styling, layout, and structure-level properties for document assembly.

#### Structure Example

```yaml
start_level: 1
render:
  REQ:
    - type: table
      attributes:
        - id:
            alias: "Identifier"
        - parent:
            alias: "Parent"
    - type: text
      mode: block
      attributes:
        - REQ:
            alias: "Requirement"
  COM:
    - type: text
      mode: block
      alias: "Comment"
```

#### Global Parameters

| Parameter | Type | Description | Default |
| --------- | ---- | ----------- | ------- |
| `start_level` | int | Starting heading level in the output document (offset) | 1 | 
| `remove_numeric_prefixes_in_headers` | bool   | Strip numeric prefixes from headings | true |
| `include_plain_text` | bool | Include plain text (non-requirements) in the output | true |
| `ignore_plain_text_prefixes`| list | Line prefixes to exclude from the output | <empty> |

#### Render Section Parameters

The `render` section of the config defines rendering parameters for corresponding artifact and non-artiface text blocks. Keys in the `render` object correspond to artifact types or block markers, correspondingly.

#### Artifact Render Configuration

Each artifact is rendered as a set of sections. Each section can be either `table` or `text`.

Every section definition shall have an `attributes` definition as following:

```yaml
render:
  <atype>:
    - type: text
      attributes:
        - id:
          alias: "Identifier"
        - parent:
          alias: "Parent"
```

Here:
- `id` and `parent` are attribute names. Shall be defined by a metamodel.
- `alias` is a name for this parameter to be used in publication: for tables - a column name; for text section - a caption.

For text sections: `mode` field (enum: `block`, `inline`) defines if output on the same line as the alias (`inline`) or on a new line (`block`).

### Non-Artifact Text Block Render Configuration

Text blocks are also rendered as a set of sections. For this version, the only section type supported is `text` in `block` and `inline` modes.

Block example with `alias = "Comment"`:
```text
**Comment**

Comment's text.
```

Inline example:
```text
**Comment**: Comment's text.
```

## Input/Output Layout & File Naming

Assembled documents are stored in the output directory (defaults to `.syntagmax/reports/` or configured output folder).

Naming convention:
```
<output_dir>/
    <INPUT_RECORD_NAME>_<YYYY-MM-DD>.md    ← Assembled Markdown document
```

## Command-Line Interface (CLI)

The publishing workflow is invoked via the `publish` command.

### Syntax
```bash
uv run syntagmax publish <section> [options]
```

### Parameters for `publish` Command

- **`<input-record-name>`** *(Mandatory)*: The name of the vault section to compile.
- **`--output <directory>`** *(Optional)*: Path to override the default output directory.

## Detailed Workflows

### Standard Document Assembly

2. Read the files belonging to the input record in lexicographical order.
3. Extract blocks in their natural order from the files.
4. Normalize structure (adjusting header offsets using `start_level`, formatting lists, and clearing prefixes according to configuration).
5. Apply block templates from `publish.yaml` to format requirements and text blocks.
6. Output a single cohesive Markdown file.

## Non-Functional Requirements & Constraints

- **Determinism**: The publishing system must be completely deterministic. Identical source structures and configurations must produce bit-for-bit identical outputs.
- **Input Immutability**: The publishing process must never alter the source project model or edit files in the vault.
- **Logging**: The system must log detailed execution metadata, including:
  - Timestamp of publication
  - Target section name
  - Execution options and parameters
  - Statistics (number of documents, requirements, tables, and images processed)
  - Any warnings or errors encountered

## Additional Tasks

- Derive a formal specification for publishing configuration YAML files in the form of JSON Schema.
- Adapt the publishing example in `example\publishing`
