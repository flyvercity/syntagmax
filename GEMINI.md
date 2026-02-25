# Syntagmax

Git-Based Requirements Management System (RMS).

## Project Overview

Syntagmax is a lightweight, git-friendly requirement management system designed to support tracing, model verification, and change detection. It utilizes a modular extractor-based architecture to process artifacts from various sources like Obsidian notes, Jupyter notebooks, and plain text files.

### Tech Stack
- **Language:** Python 3.13+
- **Dependency & Environment Management:** [uv](https://github.com/astral-sh/uv)
- **Build System:** [hatchling](https://hatch.pypa.io/)
- **CLI Framework:** [click](https://click.palletsprojects.com/)
- **Data Analysis:** [polars](https://pypolars.io/)
- **Configuration & Validation:** [pydantic](https://docs.pydantic.dev/)
- **Templating:** [Jinja2](https://jinja.palletsprojects.com/)
- **Rich Output:** [rich](https://github.com/Textualize/rich)
- **Internationalization (i18n):** [Babel](https://babel.pocoo.org/)
- **AI Integration:** Support for Ollama, Anthropic, OpenAI, Gemini, and AWS Bedrock.
- **MCP:** [Model Context Protocol](https://modelcontextprotocol.io/) server support.

## Project Structure

- `src/syntagmax/`: Core source code.
    - `cli.py`: CLI entry point (`stmx` command).
    - `main.py`: Orchestrates the processing pipeline.
    - `extract.py`: Artifact extraction logic using various drivers.
    - `extractors/`: Driver-specific extractors (`text`, `filename`, `obsidian`, `ipynb`).
    - `tree.py`: Logic for building the artifact relationship tree.
    - `analyse.py`: Tree validation and analysis.
    - `render.py`: Output rendering (tree view).
    - `metrics.py`: Metric collection and rendering.
    - `ai.py`: AI-based project analysis.
    - `mcp/`: MCP server implementation (`stmx-mcp`).
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
The main tool is `stmx`.
```powershell
# Run analysis on a project config
uv run stmx analyze path/to/rms.toml

# Verbose output with tree rendering
uv run stmx --verbose --render-tree analyze path/to/rms.toml

# AI-enabled analysis
uv run stmx --ai analyze path/to/rms.toml
```

### Running the MCP Server
```powershell
uv run stmx-mcp
```

### Maintenance Scripts
- **Update Translations:** `python scripts/update-translations.py` (requires `babel.cfg`)
- **Integration Test:** `python scripts/test-with-safir.py` (requires a sibling `safir` project)

## Development Conventions

### Code Style & Linting
- **Linting:** `ruff check .` and `flake8` are used. Configuration is in `pyproject.toml` and `.flake8`.
- **Formatting:** `ruff format` is preferred. Quote style is single quotes.
- **Line Length:** 120 characters.

### Testing
- **Framework:** `pytest` is used for testing.
- **Running Tests:** `uv run pytest`
- **Current State:** No unit tests are found in the root directory, but `.pytest_cache` indicates they may have been run. Integration tests are managed via `scripts/test-with-safir.py`.

### Internationalization (i18n)
- Localizations are stored in `src/syntagmax/resources/locales/`.
- Use `scripts/update-translations.py` to extract new messages and update `.po` files.

### Configuration
- Syntagmax projects are configured via TOML files (e.g., `rms.toml`).
- Global AI settings can be placed in `~/.syntagmax/config`.
- Environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) are supported.
