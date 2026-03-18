# MCP Mode Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the MCP mode to support SSE and stdio transports, integrated into the main CLI, performing a one-time project extraction at startup.

**Architecture:** Integrate FastMCP into `syntagmax/mcp/server.py`, exposing a `run_mcp_server` function. Register this in `syntagmax/cli.py` under a new `mcp` command group. The server will use the existing extraction logic from `main.py`.

**Tech Stack:** Python, FastMCP (mcp[cli]), Click, Uvicorn (for SSE).

---

### Task 1: Environment & Dependency Setup

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Verify and add dependencies**

Ensure `mcp[cli]` and `uvicorn` are present in `dependencies`.

```toml
dependencies = [
    # ... existing ...
    "mcp[cli]>=1.16.0",
    "uvicorn>=0.30.0",
]
```

- [ ] **Step 2: Install dependencies**

Run: `uv sync` (or `pip install .`)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add mcp[cli] and uvicorn dependencies"
```

### Task 2: Create failing tests for MCP Server

**Files:**
- Create: `tests/test_mcp.py`

- [ ] **Step 1: Write failing test for `get_artifact_content`**

```python
import pytest
from unittest.mock import MagicMock
from syntagmax.mcp.server import SyntagmaxMCPServer
from syntagmax.artifact import ARef

def test_get_artifact_content_success():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)
    
    mock_artifact = MagicMock()
    mock_artifact.contents.return_value = ["Line 1", "Line 2"]
    server.artifacts = {ARef.coerce("SRS-001"): mock_artifact}
    
    # We need to access the tool function directly or via the server's tool registry
    # For now, let's assume we test the internal logic
    content = server._get_content("SRS-001")
    assert content == "Line 1\nLine 2"

def test_get_artifact_content_not_found():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)
    server.artifacts = {}
    
    content = server._get_content("NON-EXISTENT")
    assert "not found" in content.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcp.py`
Expected: FAIL (ImportError or AttributeError)

- [ ] **Step 3: Commit**

```bash
git add tests/test_mcp.py
git commit -m "test: add failing tests for mcp server"
```

### Task 3: Overhaul MCP Server Logic

**Files:**
- Modify: `src/syntagmax/mcp/server.py`

- [ ] **Step 1: Replace old logic with new `SyntagmaxMCPServer` class**

```python
import logging as lg
from mcp.server.fastmcp import FastMCP
from syntagmax.extract import extract
from syntagmax.tree import build_tree
from syntagmax.analyse import analyse_tree
from syntagmax.errors import FatalError
from syntagmax.artifact import ARef

class SyntagmaxMCPServer:
    def __init__(self, config):
        self.config = config
        self.mcp = FastMCP("Syntagmax RMS")
        self.artifacts = {}
        self._setup_tools()

    def initialize(self):
        lg.info("Initializing MCP server: extracting artifacts...")
        artifacts, e_errors = extract(self.config)
        t_errors = build_tree(self.config, artifacts)
        a_errors = analyse_tree(self.config, artifacts)
        errors = e_errors + t_errors + a_errors
        if errors:
            raise FatalError(errors)
        self.artifacts = artifacts
        lg.info(f"Loaded {len(self.artifacts)} artifacts.")

    def _get_content(self, artifact_id: str) -> str:
        ref = ARef.coerce(artifact_id)
        if artifact := self.artifacts.get(ref):
            return "\n".join(artifact.contents())
        
        available = list(self.artifacts.keys())[:10]
        ids_str = ", ".join(str(k) for k in available)
        return f"Artifact '{artifact_id}' not found. Available IDs (first 10): {ids_str}..."

    def _setup_tools(self):
        @self.mcp.tool(name="get_artifact_content", description="Fetch the full content of a requirement artifact by its ID (e.g., 'SRS-001').")
        def get_artifact_content(artifact_id: str) -> str:
            return self._get_content(artifact_id)

    def run(self, transport, host, port):
        self.mcp.run(transport=transport, host=host, port=port)

def run_mcp_server(config, transport, host, port):
    server = SyntagmaxMCPServer(config)
    server.initialize()
    server.run(transport, host, port)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_mcp.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/syntagmax/mcp/server.py
git commit -m "feat(mcp): overhaul server logic and implement tool"
```

### Task 4: Integrate MCP into CLI

**Files:**
- Modify: `src/syntagmax/cli.py`

- [ ] **Step 1: Add `mcp` group and `run` command to `rms`**

```python
from syntagmax.mcp.server import run_mcp_server

@rms.group(help='MCP Server Management')
def mcp():
    pass

@mcp.command(help='Run the MCP server')
@click.pass_obj
@click.argument('config_path', type=click.Path(exists=True))
@click.option('--transport', type=click.Choice(['sse', 'stdio']), default='sse', help='Transport layer')
@click.option('--host', default='127.0.0.1', help='Host for SSE')
@click.option('--port', default=8000, help='Port for SSE')
def run(obj: Params, config_path: Path, transport: str, host: str, port: int):
    configurator = Config(obj, Path(config_path))
    run_mcp_server(configurator, transport, host, port)
```

- [ ] **Step 2: Verify CLI integration (help output)**

Run: `syntagmax mcp run --help`
Expected: Shows options for transport, host, and port.

- [ ] **Step 3: Commit**

```bash
git add src/syntagmax/cli.py
git commit -m "feat(cli): add mcp run command"
```

### Task 5: Final Verification with Mock Config

- [ ] **Step 1: Create mock `rms.toml`**

```bash
echo '[params]' > test_rms.toml
echo 'verbose = true' >> test_rms.toml
```

- [ ] **Step 2: Verify SSE startup**

Run: `syntagmax mcp run test_rms.toml --transport sse --port 8080`
Expected: Server starts and listens on 8080 (CTRL+C to stop).

- [ ] **Step 3: Verify stdio (dry run)**

Run: `echo '{"method": "list_tools", "params": {}}' | syntagmax mcp run test_rms.toml --transport stdio`
Expected: JSON output containing `get_artifact_content`.
