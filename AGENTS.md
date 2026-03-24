# Syntagmax

Git-Based Requirements Management System (RMS).

## Project Overview

Syntagmax is a lightweight, git-friendly requirement management system designed to support tracing, model verification, and change detection. It utilizes a modular extractor-based architecture to process artifacts from various sources like Obsidian notes, Jupyter notebooks, and plain text files.

### Tech Stack
- **Language:** Python 3.13+
- **Dependency & Environment Management:** [uv](https://github.com/astral-sh/uv)
- **Build System:** [hatchling](https://hatch.pypa.io/)
- **Parsing:** [Lark](https://github.com/lark-parser/lark) (Unified parsing for metamodel and extractors)
- **CLI Framework:** [click](https://click.palletsprojects.com/)
- **Execution Pipeline:** `graphlib.TopologicalSorter` for DAG-based step resolution.
- **Data Analysis:** [polars](https://pypolars.io/)
- **Configuration & Validation:** [pydantic](https://docs.pydantic.dev/)
- **Templating:** [Jinja2](https://jinja.palletsprojects.com/)
- **Rich Output:** [rich](https://github.com/Textualize/rich)
- **Internationalization (i18n):** [Babel](https://babel.pocoo.org/)
- **AI Integration:** Support for Ollama, Anthropic, OpenAI, Gemini, and AWS Bedrock (via IAM credentials or API keys).
- **MCP:** [Model Context Protocol](https://modelcontextprotocol.io/) server support.

## Project Structure

- `src/syntagmax/`: Core source code.
    - `cli.py`: CLI entry point (`syntagmax` command).
    - `main.py`: Orchestrates the processing pipeline using a DAG-based execution plan.
    - `utils.py`: Shared utilities including the topological execution plan resolver.
    - `extract.py`: Artifact extraction logic using various drivers.
    - `extractors/`: Driver-specific extractors (`text`, `obsidian`, `ipynb`).
    - `tree.py`: Logic for building the artifact relationship tree.
    - `analyse.py`: Tree validation and analysis.
    - `render.py`: Output rendering (tree view).
    - `metrics.py`: Metric collection and rendering.
    - `ai.py`: AI-based project analysis.
    - `impact.py`: Impact analysis logic (git-based staleness detection).
    - `git_utils.py`: Git-related utilities.
    - `mcp/`: MCP server implementation.
    - `resources/`: Shared resources, Jinja templates, and localizations.
- `docs/`: Project documentation, including `INTERNALS.md`.
- `scripts/`: Development and maintenance scripts.
- `pyproject.toml`: Project metadata and dependencies.

## Building and Running

### Development Environment
The project uses `uv` for environment management.
```powershell
uv sync
```

### Running the CLI
The main tool is `syntagmax`.
```powershell
# Run full analysis on a project config (defaults to metrics)
uv run syntagmax analyze path/to/config.toml

# Run specific step (e.g. impact analysis)
uv run syntagmax analyze path/to/config.toml impact

# Verbose output with tree rendering
uv run syntagmax --verbose --render-tree analyze path/to/config.toml
```

### Running the MCP Server
```powershell
uv run syntagmax mcp run path/to/config.toml
```

### Maintenance Scripts
- **Update Translations:** `python scripts/update-translations.py` (requires `babel.cfg`)

## Development Conventions

### Parsing and Grammars
- **Unified Library:** All parsing logic must use `Lark`.
- **Grammar Files:** Extractor-specific grammars are stored in `.lark` files within `src/syntagmax/extractors/`.
- **Transformers:** Use `lark.Transformer` to convert parse trees into internal objects (`Ref`, `dict`, etc.).
- **Obsidian Fields:** Fields in Obsidian (`[field] contents`) MUST start at the beginning of a line to be recognized.
- **Identifiers:** Grammars for `AID`, `ATYPE`, and `REVISION` support hyphens to accommodate real-world data patterns.

### Code Style & Linting
- **Linting:** `ruff check .` and `flake8` are used.
- **Formatting:** `ruff format .` is preferred. Quote style is single quotes.
- **Line Length:** 120 characters.

### Testing
- **Framework:** `pytest` is used for testing.
- **Running Tests:** `uv run pytest`
- **Unit Tests:** Found in `tests/`. Covers `TextExtractor` and `ObsidianExtractor` with various edge cases.

### Internationalization (i18n)
- Localizations are stored in `src/syntagmax/resources/locales/`.
- Use `scripts/update-translations.py` to extract new messages and update `.po` files.

### Configuration
- Syntagmax projects are configured via TOML files (e.g., `config.toml`).
- Global AI settings can be placed in `~/.syntagmax/config`.
- Environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) are supported.

## Instructions for Jules

Observe rules in `.agent/rules/`.
