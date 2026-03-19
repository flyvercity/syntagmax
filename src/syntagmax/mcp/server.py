import logging as lg
from mcp.server.fastmcp import FastMCP
from syntagmax.extract import extract
from syntagmax.tree import build_tree
from syntagmax.analyse import analyse_tree
from syntagmax.errors import FatalError
from syntagmax.artifact import ARef


class SyntagmaxMCPServer:
    def __init__(self, config, host='127.0.0.1', port=8000, sse_path='/'):
        self.config = config
        self.mcp = FastMCP('Syntagmax RMS', host=host, port=port, sse_path=sse_path)
        self.artifacts = {}
        self._setup_tools()

    def initialize(self):
        lg.info('Initializing MCP server: extracting artifacts...')
        artifacts, e_errors = extract(self.config)
        t_errors = build_tree(self.config, artifacts)
        a_errors = analyse_tree(self.config, artifacts)
        errors = e_errors + t_errors + a_errors
        if errors:
            raise FatalError(errors)
        self.artifacts = artifacts
        lg.info(f'Loaded {len(self.artifacts)} artifacts.')

    def _get_content(self, artifact_id: str) -> str:
        ref = ARef.coerce(artifact_id)
        lg.info(f'Requesting artifact {ref}')

        if artifact := self.artifacts.get(ref):
            lg.info(f'Found artifact {ref}')
            response = artifact.contents()
        else:
            lg.warning(f'Artifact {ref} not found.')
            available = list(self.artifacts.keys())[:10]
            ids_str = ', '.join(str(k) for k in available)
            response = f"Artifact '{artifact_id}' not found. Available IDs (first 10): {ids_str}..."

        lg.info(f'Responding to {ref}: {response}')
        return response

    def _setup_tools(self):
        @self.mcp.tool(
            name='get_artifact_content',
            description="Fetch the full content of a requirement artifact by its ID (e.g., 'SRS-001').",
        )
        def get_artifact_content(artifact_id: str) -> str:
            return self._get_content(artifact_id)

    def run(self, transport):
        self.mcp.run(transport=transport)


def run_mcp_server(config, host, port, sse_path='/'):
    server = SyntagmaxMCPServer(config, host=host, port=port, sse_path=sse_path)
    server.initialize()
    server.run('sse')
