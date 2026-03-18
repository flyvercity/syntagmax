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
