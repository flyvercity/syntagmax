# Syntagmax - Git-Based Requirements Management System

Syntagmax is a lightweight, git-friendly requirement management system designed to support tracing, model verification, and change detection. It uses a modular extractor-based architecture to process artifacts from various sources like Obsidian notes, Jupyter notebooks, and plain text files.

## Project Overview

- **Purpose:** Provide a robust, text-based requirements management workflow that fits seamlessly into Git.
- **Core Workflow:** 
    1. **Extraction:** Parse artifacts from files using specialized drivers (`obsidian`, `ipynb`, `text`).
    2. **Tree Building:** Establish parent-child relationships between artifacts.
    3. **Analysis:** Validate the artifact tree against a custom metamodel DSL.
    4. **Output/Metrics:** Generate tree views and collect metrics (e.g., status, verification coverage).
    5. **AI Integration:** Support for project analysis using various AI providers (OpenAI, Anthropic, Gemini, Ollama).

### Tech Stack
- **Language:** Python 3.13+
- **Dependency Management:** [uv](https://github.com/astral-sh/uv)
- **Parsing:** [Lark](https://github.com/lark-parser/lark) (Unified parsing for metamodel and extractors)
- **CLI Framework:** [click](https://click.palletsprojects.com/)
- **Data Analysis:** [polars](https://pypolars.io/)
- **Configuration & Validation:** [pydantic](https://docs.pydantic.dev/)
- **Templating:** [Jinja2](https://jinja.palletsprojects.com/)
- **Rich Output:** [rich](https://github.com/Textualize/rich)
- **Internationalization (i18n):** [Babel](https://babel.pocoo.org/)
- **MCP:** [Model Context Protocol](https://modelcontextprotocol.io/) server support.

## Project Structure

- `src/syntagmax/`: Core source code.
    - `cli.py`: CLI entry point (`syntagmax` command).
    - `main.py`: Orchestrates the processing pipeline.
    - `extract.py`: Artifact extraction logic.
    - `metamodel.py`: Logic for the custom Metamodel DSL.
    - `tree.py`: Logic for building the artifact relationship tree.
    - `mcp/`: MCP server implementation.
    - `extractors/`: Driver-specific extractors and their `.lark` grammars.
- `docs/`: Project documentation, including `INTERNALS.md`.
- `tests/`: Extensive test suite using `pytest`.
- `pyproject.toml`: Project metadata and dependencies.

## Building and Running

### Development Environment
Initialize the environment using `uv`:
```powershell
uv sync
```

### Running the CLI
The main tool is `syntagmax` (aliased as `stmx` in some documentation).
```powershell
# Run full analysis on a project config
uv run syntagmax analyze path/to/config.toml

# Verbose output with tree rendering
uv run syntagmax --verbose --render-tree analyze path/to/config.toml

# AI-enabled analysis
uv run syntagmax --ai analyze path/to/config.toml
```

### Running the MCP Server
```powershell
uv run syntagmax mcp run path/to/config.toml
```

### Running Tests
```powershell
uv run pytest
```

## Development Conventions

### Parsing and Grammars
- **Lark Only:** All new parsing logic must use `Lark`.
- **Grammar Files:** Extractor-specific grammars are stored in `.lark` files in `src/syntagmax/extractors/`.
- **Transformers:** Use `lark.Transformer` for parse tree conversion.

### Code Style
- **Linting & Formatting:** `ruff check .` and `ruff format .`.
- **Line Length:** 120 characters.
- **Quotes:** Single quotes preferred.

### Internationalization (i18n)
- Localizations are in `src/syntagmax/resources/locales/`.
- Use `python scripts/update-translations.py` to extract messages and update `.po` files.
