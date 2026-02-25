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
| `timeout_s` | No | `60.0` | Request timeout in seconds |

### Example

```toml
base = ".."

[[input]]
name = "requirements"
dir = "requirements/REQS-REFINE"
driver = "obsidian"

[[input]]
name = "fusion"
dir = "app/src/main"
driver = "text"
atype = "SRC"
filter = "**/*.kt"

[metrics]
enabled = true
output_format = "markdown"
output_file = "output/metrics.md"

[ai]
provider = "anthropic"
model = "claude-3-5-sonnet-20240620"
```

## Required Improvements

- Implement automatic change propagation
