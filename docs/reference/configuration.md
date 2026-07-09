# Configuration Reference

Syntagmax uses a TOML configuration file (default `.syntagmax/config.toml`).

## Top-level Options

| Option | Required | Description |
|--------|----------|-------------|
| `base` | Yes | Base directory path (relative to the config file) |
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
| `exclude_elements` | No | `[]` | Markdown elements to exclude at extraction time. Merged with global `[drivers.obsidian]` defaults. Valid values: `callouts`, `headings`, `horizontal_rules`, `frontmatter`. |

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

## Drivers (`[drivers]`)

Global defaults for driver-specific behaviour. Per-record settings are merged with (not override) these defaults.

### Obsidian Driver (`[drivers.obsidian]`)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `exclude_elements` | No | `[]` | Markdown elements to exclude from text blocks at extraction time. Valid values: `callouts`, `headings`, `horizontal_rules`, `frontmatter`. |
| `integration` | No | `false` | Enable reading Obsidian vault settings (e.g. `attachmentFolderPath` from `.obsidian/app.json`). |
| `root` | No | `<base_dir>/.obsidian` | Override path to the `.obsidian` directory (relative to base dir). |

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

**Element descriptions:**
- `callouts` — lines starting with `>` (Obsidian callouts / blockquotes)
- `headings` — lines starting with `#`
- `horizontal_rules` — lines consisting of three or more `-`, `*`, or `_`
- `frontmatter` — YAML frontmatter block at file start (`---` delimited)

Filtering is code-block-aware: lines inside fenced code blocks (` ``` `) are never removed.

**Example:**

```toml
[drivers.obsidian]
exclude_elements = ["callouts", "frontmatter"]
```

Per-record `exclude_elements` are merged with the global list:

```toml
[drivers.obsidian]
exclude_elements = ["frontmatter"]

[[input]]
name = "system-requirements"
dir = "SYS"
driver = "obsidian"
exclude_elements = ["callouts"]  # resolved: ["callouts", "frontmatter"]
```

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
