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
  TABLE:
    - type: text
```

#### Global Parameters

| Parameter | Type | Description | Default |
| --------- | ---- | ----------- | ------- |
| `start_level` | int | Starting heading level in the output document (offset) | 1 | 
| `remove_numeric_prefixes_in_headers` | bool   | Strip numeric prefixes from headings | true |
| `include_plain_text` | bool | Include plain text (non-requirements) in the output | true |
| `ignore_plain_text_prefixes`| list | Line prefixes to exclude from the output | <empty> |

#### Render Section Parameters

`publish.yaml` defines display templates for different object kinds (e.g. requirements, images, tables, comments).

### 3.2. Template Field Definitions

- **`type`** (enum: `table`, `text`): Presentation style of the section.
- **`mode`** (enum: `block`, `inline`): For text sections: output on the same line as the alias (`inline`) or on a new line (`block`).
- **`attributes`** (list): List of attribute names and display alias pairs for artifacts that possess attributes.
- **`alias`** (string): Alias used for non-attribute fields.

---

## 4. Input/Output Layout & File Naming

Assembled documents are stored in the output directory (defaults to `.syntagmax/reports/` or configured output folder).

Naming convention:
```
<output_dir>/
    <VAULT>_<SECTION>_<YYYY-MM-DD>.md    ← Assembled Markdown document
    <VAULT>_<SECTION>_<YYYY-MM-DD>.docx  ← Final Word document (optional, generated if --docx is requested)
```

---

## 5. Command-Line Interface (CLI)

The publishing workflow is invoked via the `publish` command.

### 5.1. Syntax
```bash
publish <section> [options]
```

### 5.2. Parameters

- **`<section>`** *(Mandatory)*: The name of the vault section to compile.
- **`--config <file>`** *(Optional)*: Path to an override configuration file.
- **`--output <directory>`** *(Optional)*: Path to override the default output directory.
- **`--docx`** *(Optional)*: Attempts to run Pandoc to compile a Word document alongside the Markdown.
- **`--doors`** *(Optional)*: Activates identifier and attribute replacement mode.
- **`--mapping <csv>`** *(Optional)*: Path to the CSV file mapping keys to replacement values for DOORS mode.
- **`--verbose`** *(Optional)*: Enables verbose console logging and trace output.

---

## 6. Detailed Workflows

### 6.1. Standard Document Assembly
1. Locate the target section. Ensure the project is parsed and the section exists in the vault.
2. Read the files belonging to the section in lexicographical order.
3. Extract blocks in their natural order from the files.
4. Normalize structure (adjusting header offsets using `start_level`, formatting lists, and clearing prefixes according to configuration).
5. Apply block templates from `publish.yaml` to format requirements and other structured blocks.
6. Output a single cohesive Markdown file.

### 6.2. DOCX Export (Pandoc Integration)
1. Generate the standard Markdown output file.
2. If the `--docx` flag is present, check for the presence of the `pandoc` executable.
3. If Pandoc is available, run it to convert the Markdown to DOCX.
4. If Pandoc is absent or fails, log the error to the publication log, preserve the successfully generated Markdown file, and exit successfully (do not crash).

### 6.3. DOORS Replacement Mode
1. When `--doors` and `--mapping <csv>` are provided, load the CSV mapping table.
2. Iterate through parsed blocks.
3. Replace requirement IDs, object IDs, and designated attribute values using the mapping.
4. If a value does not exist in the mapping file, preserve the original value.
5. Record the number of successful replacements in the publication log.

---

## 7. Non-Functional Requirements & Constraints

- **Determinism**: The publishing system must be completely deterministic. Identical source structures and configurations must produce bit-for-bit identical outputs.
- **Input Immutability**: The publishing process must never alter the source project model or edit files in the vault.
- **Logging**: The system must log detailed execution metadata, including:
  - Timestamp of publication
  - Target section name
  - Execution options and parameters
  - Statistics (number of documents, requirements, tables, and images processed)
  - Details on DOORS replacements and Pandoc exit status
  - Any warnings or errors encountered
