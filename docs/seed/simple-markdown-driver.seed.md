# Seed Spec: Simple Markdown Driver

We need a simpler way to manage standalone artifacts (like tasks, release notes, or simple specifications) without all the heavy markup of the default Obsidian driver. 

Currently, the Obsidian driver expects a lot of custom grammar markers like `[id]`, `[contents]`, and nested `attrs` block inside the YAML frontmatter. This is great for document-embedded requirements but too heavy for files where the entire file represents one artifact (e.g. one task per file).

We want to introduce a new driver called `simple-markdown`.

## Core Features

1. **One File, One Artifact**: By default, each markdown file in the input directory is parsed as a single artifact.
2. **Flat YAML Frontmatter**: The file must start with a standard YAML frontmatter block (enclosed in `---`). All keys in this frontmatter are parsed as direct attributes of the artifact (no nested `attrs:` key needed).
3. **Implicit ID**: If no `id` is specified in the frontmatter, the driver should automatically derive the ID from the filename (e.g. `TASK-001.md` gets `id = "TASK-001"`).
4. **Body as Contents**: The markdown body (everything after the frontmatter closing `---`) is automatically assigned to the `contents` attribute.
5. **No Parser Markup**: No custom markers (`[attribute]`) or syntax tags are required in the body.

## Example File

`tasks/TASK-IMPACT-REQ-001-SYS-001.md`:
```markdown
---
id: TASK-IMPACT-REQ-001-SYS-001
status: open
parent_revision: abc1234
child_revision: old1234
---
# Verify REQ-001 after SYS-001 change

Verify that REQ-001 is still consistent with the updated SYS-001 and update the tracing reference.
```

## Configuration

In `config.toml`, users should be able to specify the driver:

```toml
[[input]]
name = "tasks"
dir = ".syntagmax/tasks"
driver = "simple-markdown"
default_atype = "TASK"
```

## Tasks

- Create `SimpleMarkdownExtractor` in `src/syntagmax/extractors/simple_markdown.py`.
- Register the `simple-markdown` driver in `src/syntagmax/extractors/obsidian.py` or where driver mappings are defined.
- Parse YAML frontmatter flatly using `ruamel.yaml` or a simple regex parser.
- Assign the rest of the file to the `contents` field.
- Extract filename base as ID if frontmatter lacks an `id` attribute.
- Add unit tests for flat frontmatter extraction and filename ID fallback.
- Add an example to the docs showing how to configure it.
