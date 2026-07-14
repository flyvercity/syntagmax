# Configuration Reference

Syntagmax uses a TOML configuration file (default `.syntagmax/config.toml`).

For a detailed explanation of how Syntagmax handles different directories, relative path resolution, and editor integration (e.g., Obsidian), see the [Paths Reference](paths.md).

## Top-level Options

| Option | Required | Description |
|--------|----------|-------------|
| `base` | Yes | Base directory path (relative to the config file). |
| `publish` | No | Global publish config file path (relative to config file directory). See [Publishing Reference](publishing.md). |
| `input` | Yes | List of input source definitions |
| `drivers` | No | Driver-specific global defaults |
| `metrics` | No | Metrics collection settings |
| `metamodel` | No | Metamodel configuration |

## Input Sources (`[[input]]`)

Each input defines a source of requirements or artifacts:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | — | Input source name |
| `dir` | Yes | — | Subdirectory relative to base directory |
| `driver` | Yes | — | Driver type: `obsidian`, `ipynb`, `markdown`, etc. |
| `filter` | No | Driver-specific | File filter pattern (glob). Defaults: `obsidian` → `**/*.md`, `ipynb` → `**/*.ipynb`, `markdown` → `**/*.md` |
| `atype` | No | `REQ` | Default artifact type for this source |
| `marker` | No | *atype* | Custom marker for artifacts (e.g., `[SYS]` in Markdown). Defaults to `atype`. |
| `markers` | No | `[]` | List of fragment markers for non-artifact text blocks (e.g., `["COM", "NOTE"]`). Obsidian driver only. |
| `publish` | No | — | Path to a per-record publish configuration file (relative to the base directory). If the file is not found, Syntagmax raises an error. See [Publishing Reference](publishing.md). |
| `exclude_elements` | No | `[]` | Markdown elements to exclude at extraction time. Each entry is an object with `name` and optional `mode`. Merged with global `[drivers.obsidian]` defaults. See [Element Exclusion](#element-exclusion) below. |

## Marked Fragments (Obsidian Driver)

The `markers` option allows tagging non-artifact text blocks with named markers such as `[COM]...[/COM]` or `[NOTE]...[/NOTE]`. These marked fragments are extracted as `TextBlock`s with a `marker` field set, which can later influence publication filtering.

**Rules:**
- Markers are case-insensitive (`[com]...[/COM]` is valid)
- Marker values are stored in uppercase (e.g., `COM`, `NOTE`)
- Fragment markers must not collide with the artifact marker (fatal config error)
- No nesting or overlap between markers
- Only supported for the `obsidian` driver

**Example config:**

```toml
[[input]]
name = "system-requirements"
dir = "SYS"
driver = "obsidian"
markers = ["COM", "NOTE"]
```

**Example markdown:**

```text
This is a preamble. [COM]This is a comment.[/COM]
[note]This is a note.[/note]
Some more text.
[SYS]
Requirement body
[id] SYS-001
[/SYS]
```

This produces the following blocks:
- Regular text: `This is a preamble. `
- Comment fragment (marker=`COM`): `This is a comment.`
- Regular text: `\nSome more text.\n`
- Note fragment (marker=`NOTE`): `This is a note.`
- Artifact: `SYS-001`

For detailed syntax, marker formats, ID rules, and automatic ID assignment, see the [Obsidian driver reference](obsidian.md#fragment-markers).

## Drivers (`[drivers]`)

Global defaults for driver-specific behaviour. Per-record settings are merged with (not override) these defaults.

### Obsidian Driver (`[drivers.obsidian]`)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `exclude_elements` | No | `[]` | Markdown elements to exclude from text blocks at extraction time. Each entry is an object with `name` and optional `mode`. See [Element Exclusion](#element-exclusion) below. |
| `integration` | No | `false` | Enable reading Obsidian vault settings (e.g. `attachmentFolderPath`, `strictLineBreaks` from `.obsidian/app.json`). |
| `root` | No | `<base_dir>/.obsidian` | Override path to the `.obsidian` directory (relative to base dir). |
| `strict_line_breaks` | No | `"on"` | Line break handling mode. See [Strict Line Breaks](#strict-line-breaks) below. |

#### Obsidian Vault Integration

When `integration = true`, Syntagmax reads the Obsidian vault settings file (`.obsidian/app.json`) to discover the configured `attachmentFolderPath`. During publishing, image references (`![[image.png]]`) are resolved against this folder before falling back to the vault-wide file scan.

**Path resolution rules:**
- Vault-relative paths (e.g. `"attachments/pics"`) are resolved relative to the project base directory.
- Note-relative paths (e.g. `"./attachments"` or `"."`) are resolved relative to the current source note's directory.

If `.obsidian/app.json` is missing, unreadable, or does not contain `attachmentFolderPath`, a warning is logged and publishing falls back to the standard vault-wide image scan.

**Example:**

```toml
[drivers.obsidian]
integration = true
root = ".obsidian"  # optional, this is the default
```

#### Strict Line Breaks

Controls how single newlines in Obsidian Markdown source content are treated during extraction.

Obsidian by default treats a single newline as a visible line break (`<br>`). This is non-standard Markdown behavior — the Markdown spec treats single newlines as whitespace. The `strict_line_breaks` setting allows Syntagmax to match whichever behavior the user's vault is configured for.

**Accepted values:**

| Value | Meaning |
|-------|---------|
| `"on"` / `"true"` / `true` | Strict mode (standard Markdown). Single newlines are whitespace. No transformation applied. **(default)** |
| `"off"` / `"false"` / `false` | Obsidian relaxed mode. Single newlines become hard breaks (`  \n`) during extraction. |
| `"auto"` | Read the `strictLineBreaks` setting from Obsidian's `.obsidian/app.json`. Requires `integration = true`. |

When strict mode is OFF, the transformation converts single newlines to Markdown hard breaks (two trailing spaces + newline) at extraction time. This ensures that published output and Pandoc exports preserve the author's intended line breaks.

**Transformation rules:**
- Lines inside fenced code blocks are never modified.
- Empty/whitespace-only lines (paragraph separators) are never modified.
- Lines preceding a paragraph separator are never modified.
- Markdown block-level elements (headings, tables, lists, thematic breaks, HTML blocks) are never modified.
- Already-existing hard breaks (trailing `  ` or `\`) are not doubled.
- CRLF line endings are preserved.

**Note:** Syntagmax defaults to `"on"` (standard Markdown) while Obsidian itself defaults to relaxed breaks. Users wanting vault-consistent behavior should use `"auto"` (with `integration = true`) or `"off"`.

**Example:**

```toml
[drivers.obsidian]
strict_line_breaks = "off"
```

Or using `auto` mode with vault integration:

```toml
[drivers.obsidian]
integration = true
strict_line_breaks = "auto"
```

**Error:** Setting `strict_line_breaks = "auto"` without `integration = true` is a fatal configuration error.

#### Element Exclusion

Each entry in `exclude_elements` is an object with two fields:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | — | Element to exclude: `callouts`, `headings`, `horizontal_rules`, `frontmatter`, `tags` |
| `mode` | No | `string-on-start` | Removal mode: `only`, `string`, or `string-on-start` |

**Removal modes:**

| Mode | Behaviour |
|------|-----------|
| `only` | Remove the element marker/prefix but keep surrounding text on the line |
| `string` | Remove the entire line if the element is present anywhere |
| `string-on-start` | Remove the entire line if the element is the first non-whitespace |

**Mode semantics by element:**

| Element | `only` | `string` | `string-on-start` (default) |
|---------|--------|----------|----------------------------|
| `callouts` | Strip `> ` prefix, keep text (preserve indentation) | Remove line | Remove line |
| `headings` | Strip `# ` prefix, keep text (preserve indentation) | Remove line | Remove line |
| `horizontal_rules` | Remove line | Remove line | Remove line |
| `frontmatter` | Remove block | Remove block | Remove block |
| `tags` | Strip `#tag` inline, keep surrounding text | Remove entire line if any tag present | Remove line if tag starts it; strip inline otherwise |

For `frontmatter` and `horizontal_rules`, all three modes behave identically (complete removal).

Filtering is code-block-aware: lines inside fenced code blocks (` ``` `) are never modified. Tags inside inline code spans (`` `#tag` ``) are also protected.

**Example:**

```toml
[drivers.obsidian]
exclude_elements = [
    {name = "frontmatter"},
    {name = "callouts", mode = "only"},
    {name = "tags", mode = "string-on-start"},
]
```

Per-record `exclude_elements` are merged (union) with the global list. Per-record mode takes precedence for the same element name:

```toml
[drivers.obsidian]
exclude_elements = [{name = "frontmatter"}, {name = "tags", mode = "only"}]

[[input]]
name = "system-requirements"
dir = "SYS"
driver = "obsidian"
exclude_elements = [{name = "callouts"}, {name = "tags", mode = "string"}]
# resolved: frontmatter (string-on-start), callouts (string-on-start), tags (string)
```

**Tags example:**

With `mode = "string-on-start"`, lines starting with a tag are removed entirely, while mid-line tags are stripped inline:

```toml
[drivers.obsidian]
exclude_elements = [{name = "tags", mode = "string-on-start"}]
```

Given source text:
```text
#internal remove this entire line
This requirement relates to safety. #safety #performance/telemetry

See `#example` in the code.
```

The extracted text block will contain:
```text
This requirement relates to safety.

See `#example` in the code.
```

Tags inside inline code, fenced code blocks, and URL anchors are never stripped.

## Metrics (`[metrics]`)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `enabled` | No | `false` | Enable metrics collection |
| `requirement_type` | No | `REQ` | Requirement type to include |
| `status_field` | No | `status` | Status attribute name |
| `verify_field` | No | `verify` | Verify attribute name |
| `tbd_marker` | No | `TBD` | TBD detection marker |

## Impact Analysis (`[impact]`)

Impact analysis helps identify potentially outdated artifacts by comparing their parent revisions.

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `enabled` | No | `false` | Enable impact analysis |

## Metamodel (`[metamodel]`)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `filename` | No | — | Path to the `.syntagmax` file defining the project's metamodel. |

## AI Configuration (`[ai]`)

AI analysis configuration. Settings can also be placed in `~/.syntagmax/config` (global configuration) which are overridden by the project configuration.

Environment variables can also be used for API keys (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`). Configuration file values take precedence.

**Note on AWS Bedrock:** Currently, only Anthropic Claude models are supported on Bedrock. `boto3` must be installed manually to use Bedrock.

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `provider` | No | `ollama` | AI provider: `ollama`, `anthropic`, `openai`, `gemini`, `bedrock` |
| `model` | No | *Provider Default* | Model name to use (e.g. `gpt-4o`, `claude-3-opus`) |
| `ollama_host` | No | `http://localhost:11434` | Ollama host URL |
| `anthropic_api_key` | No | — | Anthropic API Key |
| `openai_api_key` | No | — | OpenAI API Key |
| `gemini_api_key` | No | — | Google Gemini API Key |
| `aws_access_key_id` | No | — | AWS Access Key ID |
| `aws_secret_access_key` | No | — | AWS Secret Access Key |
| `aws_region_name` | No | — | AWS Region Name |
| `aws_api_key` | No | — | AWS Bedrock API Key |
| `timeout_s` | No | `60.0` | Request timeout in seconds |

## Full Example

```toml
base = ".."

[[input]]
name = "requirements"
dir = "requirements/REQS"
driver = "obsidian"

[[input]]
name = "implementation"
dir = "app/src/main"
driver = "text"
atype = "SRC"
filter = "**/*.kt"

[metrics]
enabled = true

[metamodel]
filename = "project.syntagmax"

[ai]
provider = "anthropic"
model = "claude-sonnet-4-6"
```
