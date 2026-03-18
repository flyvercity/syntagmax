# Design Spec: MCP Mode Overhaul

## Status: Draft
## Date: 2026-03-18
## Author: Gemini CLI

## 1. Overview
Overhaul the Model Context Protocol (MCP) integration in `syntagmax` to support both Streaming (SSE) and Standard I/O (stdio) transports. The MCP server will be integrated into the main CLI and will perform a full project extraction (extract, build tree, analyse) once at startup, providing a tool to fetch artifact contents.

## 2. Goals
- Replace the standalone, hardcoded MCP script with a first-class CLI command: `syntagmax mcp run`.
- Support SSE (Streaming) transport for network-based access.
- Retain stdio transport for local use/development.
- Mirror the extraction logic from `src/syntagmax/main.py`.
- Provide a single robust tool: `get_artifact_content`.

## 3. Architecture & Components

### 3.1 CLI Integration (`src/syntagmax/cli.py`)
- Add a new `mcp` command group to the `rms` entry point.
- Implement the `run` command:
  - Usage: `syntagmax mcp run <config-file> [--transport sse|stdio] [--host 127.0.0.1] [--port 8000]`
  - Orchestrates: `Params` -> `Config` -> `server.run_mcp_server`.

### 3.2 MCP Server (`src/syntagmax/mcp/server.py`)
- Define a `run_mcp_server(config, transport, host, port)` function.
- Initialization Flow (Startup):
  1. `artifacts, e_errors = extract(config)`
  2. `t_errors = build_tree(config, artifacts)`
  3. `a_errors = analyse_tree(config, artifacts)`
  4. Raise `FatalError` if errors occur during startup.
- FastMCP Instance:
  - Name: `Syntagmax RMS`
  - Version: `0.1.0` (or derived from project)

### 3.3 MCP Tools
- **`get_artifact_content(artifact_id: str) -> str`**:
  - **Description**: "Fetch the full content of a requirement artifact by its ID (e.g., 'SRS-001')."
  - Coerces `artifact_id` to `ARef`.
  - Retrieves artifact from the pre-computed dictionary.
  - Returns the joined lines of artifact contents.
  - Handles "not found" cases gracefully.
  - *Note*: This replaces the deprecated `fetch-requirement` tool.

## 4. Data Flow
1. **User** runs `syntagmax mcp run rms.toml --transport sse`.
2. **CLI** parses arguments and initializes the environment.
3. **Server** performs full extraction and analysis (one-time).
4. **FastMCP** starts the SSE server on the specified port.
5. **MCP Client** calls `get_artifact_content`.
6. **Server** returns the requested content from memory.

## 5. Error Handling
- Startup errors (extraction/parsing) will prevent the server from starting and report errors to the terminal.
- Tool-level errors (missing artifact IDs) will be returned as strings to the LLM to facilitate recovery.

## 6. Testing Strategy
- **Manual Verification**: Run the server in SSE mode and verify it's reachable via `curl` or an MCP inspector.
- **Unit Tests**: Test the `get_artifact_content` logic with a mock artifact dictionary.
- **Integration Tests**: Verify the CLI command correctly initializes the server.
