*This is vastly a work-in-progress*

# Syntagmax - Git-Based Requirements Management System

Fully git-friendly lightweight requirements management system with tracing model verification, change detection, and propagation.

## Configuration

Syntagmax uses a TOML configuration file (default `.syntagmax/config.toml`).

### Top-level options

| Option | Required | Description |
|--------|----------|-------------|
| `base` | Yes | Base directory path (relative to the config file) |
| `input` | Yes | List of input source definitions |
| `metrics` | No | Metrics collection settings |
| `metamodel` | No | Metamodel configuration |

### Input sources (`[[input]]`)

Each input defines a source of requirements or artifacts:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | — | Input source name |
| `dir` | Yes | — | Subdirectory relative to base directory |
| `driver` | Yes | — | Driver type: `obsidian`, `ipynb`, `markdown`, etc. |
| `filter` | No | Driver-specific | File filter pattern (glob). Defaults: `obsidian` → `**/*.md`, `ipynb` → `**/*.ipynb`, `markdown` → `**/*.md` |
| `atype` | No | `REQ` | Default artifact type |

### Metrics (`[metrics]`)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `enabled` | No | `false` | Enable metrics collection |
| `requirement_type` | No | `REQ` | Requirement type to include |
| `status_field` | No | `status` | Status attribute name |
| `verify_field` | No | `verify` | Verify attribute name |
| `tbd_marker` | No | `TBD` | TBD detection marker |
| `output_format` | No | `rich` | Output format: `rich` or `markdown` |
| `output_file` | No | `console` | Output file name (`console` for stdout) |
| `template` | No | — | Path to custom Jinja template |
| `locale` | No | `en` | Locale code for localization |

### Impact Analysis (`[impact]`)

Impact analysis helps identify potentially outdated artifacts by comparing their parent revisions.

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `enabled` | No | `false` | Enable impact analysis |
| `output_format` | No | `rich` | Output format: `rich` or `markdown` |
| `output_file` | No | `console` | Output file name (`console` for stdout) |
| `template` | No | — | Path to custom Jinja template |
| `locale` | No | `en` | Locale code for localization |

### Metamodel (`[metamodel]`)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `filename` | No | — | Path to the `.syntagmax` file defining the project's metamodel. |

### AI Configuration (`[ai]`)

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

### Example

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
output_format = "markdown"
output_file = "output/metrics.md"

[metamodel]
filename = "project.syntagmax"

[ai]
provider = "anthropic"
model = "claude-sonnet-4-6"
```

## Git Integration

Syntagmax automatically extracts revision history for each artifact using Git. This provides traceability and helps track changes over time.

### Revision Descriptors

Each artifact is attached with a set of revisions. A revision includes:
- **Short Hash**: The 7-character commit hash.
- **Timestamp**: Date and time of the commit.
- **Author**: Email of the commit author.

### Extraction Logic

- **Text-based artifacts** (e.g., source code sections, Obsidian requirements): Syntagmax uses `git blame` to identify all commits that affected the specific lines where the artifact is defined.
- **Sidecar artifacts**: Syntagmax identifies the last commit that affected the primary file (e.g., an image) and all commits that affected the sidecar metadata file.

### Disabling Git Integration

If you want to skip git history extraction (e.g., if you are not in a git repository or want to speed up analysis), use the `--no-git` flag:

```bash
syntagmax analyze --no-git
```

## Metamodel DSL

Syntagmax allows defining a custom metamodel for artifacts and their attributes using a simple DSL. This metamodel is used for static validation of requirements and other artifacts.

**Companion VS Code Extension:** [syntagmax-vscode](https://github.com/flyvercity/syntagmax-vscode)

### Example

```model
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute parent is optional reference to parent
    attribute status is mandatory enum [draft, active, retired]
    attribute verify is optional string
    attribute priority is mandatory integer
```

The attributes `id` and `contents` are always mandatory for all artifacts, but the type is flexible.

### Syntax Reference

Python-style comments (`# ...`) are supported.

| Rule | Description |
|------|-------------|
| `artifact <NAME>:` | Defines a new artifact type. Rules must be indented. |
| `attribute <ATTR> is <presence> [multiple] <type>` | Defines an attribute rule. |

**Presence:** `mandatory` or `optional`.

**Modifier:**
- `multiple`: (Optional) Allows an attribute to have multiple values. Multiple values are extracted into a list. If a `multiple` attribute is missing, it defaults to an empty list `[]`.

**Types:**
- `string`: Any text.
- `integer`: A whole number.
- `boolean`: `true` or `false`.
- `reference [to parent]`: A reference to another artifact (e.g., `SRS-001`). The optional `to parent` modifier marks the attribute as a parent indicator, used for building the artifact hierarchy. 
  - **Nominal Revision**: You can specify a parent's revision using the `@` symbol: `parent: SRS-001@c2d94e4`. This allows for impact analysis to identify if a requirement is outdated relative to its parent.
- `enum [<values>]`: A fixed set of allowed values (comma-separated).

### Impact Analysis Logic

When impact analysis is enabled (`[impact] enabled = true`), Syntagmax performs the following checks:

1. **Via Commit**: If a parent reference includes a revision (e.g., `SRS-001@c2d94e4`), Syntagmax compares it with the parent's actual latest revision. If they differ, the link is marked as suspicious.
2. **Via Timestamp**: If no revision is specified and the metamodel trace mode is `timestamp`, the link is marked as suspicious if the parent was modified later than the artifact.

Suspicious links are highlighted in the artifact tree (printed in yellow) and included in the impact analysis report.

> **Note**: Impact analysis requires a clean git worktree. You can bypass this check using the `--allow-dirty-worktree` flag.

### Trace Modes

Metamodel traces can specify an analysis mode:

```model
trace from REQ to SYS is mandatory via commit
trace from SYS to ARCH is optional via timestamp
```

- `via commit`: Requires specific revision pinning in the artifact (e.g. `parent: SYS-001@c2d94e4`).
- `via timestamp`: Uses modification times to detect potential staleness. Defaults to `older` nominal revision if not specified.

### Examples of multiple attributes

Multiple values can be specified by repeating the attribute:

```
[<
ID = REQ-1
tag = security
tag = performance
>>>
This requirement has multiple tags.
>]
```

In this case, `artifact.fields['tag']` will be `['security', 'performance']`.

In Obsidian (YAML):
```yaml
attrs:
  author:
    - Alice
    - Bob
```
This will result in `artifact.fields['author']` being `['Alice', 'Bob']`.

## Required Improvements

- Implement automatic change propagation
- Enhance AI-based analysis and tracing
- Expand VS Code extension features (LSP support)
