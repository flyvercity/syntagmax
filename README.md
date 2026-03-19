*This is vastly a work-in-progress*

# Syntagmax - Git-Based Requirements Management System

Fully git-friendly lightweight requirements management system with tracing model verification, change detection, and propagation.

## Configuration

Syntagmax uses a TOML configuration file (typically `rms.toml` or similar).

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

## Metamodel DSL

Syntagmax allows defining a custom metamodel for artifacts and their attributes using a simple DSL. This metamodel is used for static validation of requirements and other artifacts.

**Companion VS Code Extension:** [syntagmax-vscode](https://github.com/flyvercity/syntagmax-vscode)

### Example

```model
artifact REQ:
    attribute id is mandatory string
    attribute contents is mondatory string
    attribute status is mandatory enum [draft, active, retired]
    attribute verify is optional string
    attribute priority is mandatory integer
```

The attributes `id` and `contents` are always mandatory for all artifacts, but the type is flexible.

### Syntax Reference

| Rule | Description |
|------|-------------|
| `artifact <NAME>:` | Defines a new artifact type. Rules must be indented. |
| `attribute <ATTR> is <presence> <type>` | Defines an attribute rule. |

**Presence:** `mandatory` or `optional`.

**Types:**
- `string`: Any text.
- `integer`: A whole number.
- `boolean`: `true` or `false`.
- `enum [<values>]`: A fixed set of allowed values (comma-separated).

## Required Improvements

- Implement automatic change propagation
- Enhance AI-based analysis and tracing
- Expand VS Code extension features (LSP support)
