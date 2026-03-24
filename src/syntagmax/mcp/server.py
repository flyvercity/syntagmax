import logging as lg
from mcp.server.fastmcp import FastMCP
from syntagmax.extract import extract, build_artifact_map
from syntagmax.tree import build_tree, populate_pids
from syntagmax.analyse import analyse_tree
from syntagmax.errors import FatalError


class SyntagmaxMCPServer:
    def __init__(self, config, host='127.0.0.1', port=8000, sse_path='/'):
        self.config = config
        self.mcp = FastMCP('Syntagmax RMS', host=host, port=port, sse_path=sse_path)
        self.artifacts = {}
        self._setup_tools()

    def initialize(self):
        lg.info('Initializing MCP server: extracting artifacts...')
        artifacts_list, e_errors = extract(self.config)
        artifacts, v_errors = build_artifact_map(artifacts_list)
        populate_pids(self.config, artifacts)
        t_errors = build_tree(self.config, artifacts)
        a_errors = analyse_tree(self.config, artifacts)
        errors = e_errors + v_errors + t_errors + a_errors
        if errors:
            raise FatalError(errors)
        self.artifacts = artifacts
        lg.info(f'Loaded {len(self.artifacts)} artifacts.')

    def _get_content(self, artifact_id: str) -> str:
        lg.info(f'Requesting artifact {artifact_id}')

        if artifact := self.artifacts.get(artifact_id):
            lg.info(f'Found artifact {artifact_id}')

            lines = [f'# Artifact: {artifact.aid} ({artifact.atype})', '']

            if artifact.location:
                lines.append(f'**Location**: {artifact.location}')

            if rev := artifact.latest_revision:
                lines.append(f'**Latest Revision**: {rev}')

            lines.append('')

            if artifact.parent_links:
                lines.append('## Parents')
                for link in artifact.parent_links:
                    suspicious = ' ⚠️ (suspicious)' if link.is_suspicious else ''
                    rev_info = f' @ {link.nominal_revision}' if link.nominal_revision else ''
                    lines.append(f'- {link.pid}{rev_info}{suspicious}')
                lines.append('')

            if artifact.children:
                lines.append('## Children')
                for cid in sorted(artifact.children):
                    lines.append(f'- {cid}')
                lines.append('')

            lines.append('## Fields')
            for key, value in sorted(artifact.fields.items()):
                if key == 'contents':
                    continue
                if isinstance(value, list):
                    lines.append(f'- **{key}**:')
                    for item in value:
                        lines.append(f'  - {item}')
                else:
                    lines.append(f'- **{key}**: {value}')
            lines.append('')

            if contents := artifact.fields.get('contents'):
                lines.append('## Content')
                lines.append('```')
                lines.append(str(contents))
                lines.append('```')

            response = '\n'.join(lines)
        else:
            lg.warning(f'Artifact {artifact_id} not found.')
            available = list(self.artifacts.keys())[:10]
            ids_str = ', '.join(str(k) for k in available)
            response = f"Artifact '{artifact_id}' not found. Available IDs (first 10): {ids_str}..."

        lg.info(f'Responding to {artifact_id}')
        return response

    def _list_artifacts(self) -> str:
        if not self.artifacts:
            return 'No artifacts loaded.'

        lines = ['# Available Artifacts', '']
        # Filter out ROOT artifact
        visible_artifacts = {aid: a for aid, a in self.artifacts.items() if aid != 'ROOT'}

        for aid, artifact in sorted(visible_artifacts.items()):
            summary = artifact.fields.get('title') or artifact.fields.get('summary') or ''
            if summary:
                lines.append(f'- **{aid}** ({artifact.atype}): {summary}')
            else:
                lines.append(f'- **{aid}** ({artifact.atype})')

        return '\n'.join(lines)

    def _search_artifacts(self, query: str) -> str:
        query = query.lower()
        results = []
        for aid, artifact in self.artifacts.items():
            if aid == 'ROOT':
                continue

            # Search in ID, Type
            match = query in aid.lower() or query in artifact.atype.lower()

            # Search in fields
            if not match:
                for val in artifact.fields.values():
                    if isinstance(val, list):
                        if any(query in str(v).lower() for v in val):
                            match = True
                            break
                    elif query in str(val).lower():
                        match = True
                        break

            if match:
                results.append(artifact)

        if not results:
            return f"No artifacts found matching '{query}'."

        lines = [f"# Search Results for '{query}'", '']
        for artifact in sorted(results, key=lambda a: a.aid):
            summary = artifact.fields.get('title') or artifact.fields.get('summary') or ''
            if summary:
                lines.append(f'- **{artifact.aid}** ({artifact.atype}): {summary}')
            else:
                lines.append(f'- **{artifact.aid}** ({artifact.atype})')

        return '\n'.join(lines)

    def _setup_tools(self):
        @self.mcp.tool(
            name='get_artifact_content',
            description="Fetch the full content and metadata of a requirement artifact by its ID (e.g., 'SRS-001').",
        )
        def get_artifact_content(artifact_id: str) -> str:
            return self._get_content(artifact_id)

        @self.mcp.tool(
            name='list_artifacts',
            description='List all available requirement artifacts with their types and summaries.',
        )
        def list_artifacts() -> str:
            return self._list_artifacts()

        @self.mcp.tool(
            name='search_artifacts',
            description='Search for requirement artifacts by a query string in their ID, type, or fields.',
        )
        def search_artifacts(query: str) -> str:
            return self._search_artifacts(query)

    def run(self, transport):
        self.mcp.run(transport=transport)


def run_mcp_server(config, host, port, sse_path='/', transport='stdio'):
    server = SyntagmaxMCPServer(config, host=host, port=port, sse_path=sse_path)
    server.initialize()
    server.run(transport)
