import ipaddress
import logging as lg
import re

import yaml
from mcp.server.fastmcp import FastMCP
from syntagmax.extract import extract, build_artifact_map
from syntagmax.tree import build_tree, populate_pids
from syntagmax.analyse import analyse_tree
from syntagmax.errors import FatalError
from syntagmax.edit import _generate_id, _resolve_schema
from syntagmax.id_utils import count_num_macros, extract_number_from_id


class SyntagmaxMCPServer:
    def __init__(self, config, host='127.0.0.1', port=8000, sse_path='/'):
        self.config = config
        self.host = host
        self.mcp = FastMCP('Syntagmax RMS', host=host, port=port, sse_path=sse_path)
        self.artifacts = {}
        self._setup_tools()

    def initialize(self):
        lg.info('Initializing MCP server: extracting artifacts...')
        errors: list[str] = []
        artifacts_list = extract(self.config, errors)
        artifacts = build_artifact_map(artifacts_list, errors)
        populate_pids(self.config, artifacts, errors)
        build_tree(self.config, artifacts, errors)
        analyse_tree(self.config, artifacts, errors)

        if errors:
            raise FatalError([str(error) for error in errors])

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

    def _create_requirement(self, record_name: str, title: str, contents: str, attributes: dict[str, str] | None = None) -> str:
        try:
            loopback_host = ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            loopback_host = self.host.lower() == 'localhost'
        if not loopback_host:
            return 'Requirement creation is only available when the MCP server is bound to localhost.'

        record = next((record for record in self.config.input_records() if record.name == record_name), None)
        if record is None:
            return f'Input record "{record_name}" not found.'
        if record.driver not in ('obsidian', 'simple-markdown'):
            return f'Input record "{record_name}" uses unsupported driver "{record.driver}".'
        if not title.strip() or not contents.strip():
            return 'Title and contents must not be empty.'

        attributes = attributes or {}
        reserved = {'id', 'atype', 'contents', 'title'}
        if any(key.lower() in reserved for key in attributes):
            return 'Attributes must not include id, atype, contents, or title.'

        atype = record.default_atype
        schema = _resolve_schema('', atype, self.config)
        if count_num_macros(schema) != 1:
            return f'Artifact type "{atype}" must have an ID schema with exactly one {{num}} field.'

        max_number = max(
            (
                number
                for artifact in self.artifacts.values()
                if artifact.atype == atype
                if (number := extract_number_from_id(artifact.aid, schema, atype)) is not None
            ),
            default=0,
        )
        artifact_id = _generate_id(schema, atype, max_number + 1)
        if re.search(r'[<>:"/\\|?*\x00-\x1f]', artifact_id) or artifact_id in ('.', '..'):
            return f'Generated artifact ID "{artifact_id}" cannot be used as a file name.'

        record_dir = record.record_base.resolve()
        filepath = record_dir / f'{artifact_id}.md'
        if filepath.parent != record_dir:
            return f'Generated artifact ID "{artifact_id}" cannot be used as a file name.'

        contents = contents.rstrip('\r\n')
        if record.driver == 'simple-markdown':
            frontmatter = {'id': artifact_id, 'title': title, **attributes}
            document = f'---\n{yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)}---\n{contents}\n'
        else:
            if not re.fullmatch(r'[a-zA-Z0-9_-]+', record.marker):
                return f'Input record "{record_name}" has an invalid Obsidian artifact marker.'
            if any(line.lstrip().startswith('[') or line.lstrip().lower().startswith('```yaml') for line in contents.splitlines()):
                return 'Obsidian requirement contents cannot contain lines starting with "[" or a YAML code fence.'
            fields = {'title': title, **attributes}
            yaml_block = yaml.safe_dump({'attrs': fields}, sort_keys=False, allow_unicode=True)
            document = f'[{record.marker}]\n{contents}\n[id] {artifact_id}\n```yaml\n{yaml_block}```\n'

        record_dir.mkdir(parents=True, exist_ok=True)
        try:
            with filepath.open('x', encoding='utf-8') as file:
                file.write(document)
        except FileExistsError:
            return f'File already exists for artifact ID "{artifact_id}".'
        except Exception:
            filepath.unlink(missing_ok=True)
            raise

        existing_artifacts = self.artifacts
        record.filepaths.append(filepath)
        try:
            self.initialize()
        except Exception as error:
            record.filepaths.remove(filepath)
            filepath.unlink(missing_ok=True)
            if not isinstance(error, FatalError):
                raise
            return f'Could not create requirement: {error}'

        if artifact_id not in self.artifacts:
            record.filepaths.remove(filepath)
            filepath.unlink(missing_ok=True)
            self.artifacts = existing_artifacts
            return f'Could not create requirement: artifact "{artifact_id}" was not extracted.'

        return f'Created {atype} requirement "{artifact_id}" at {filepath}.'

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

        @self.mcp.tool(
            name='create_requirement',
            description='Create a requirement in a configured Obsidian or simple-markdown input record.',
        )
        def create_requirement(record_name: str, title: str, contents: str, attributes: dict[str, str] | None = None) -> str:
            return self._create_requirement(record_name, title, contents, attributes)

    def run(self, transport):
        self.mcp.run(transport=transport)


def run_mcp_server(config, host, port, sse_path='/', transport='stdio'):
    server = SyntagmaxMCPServer(config, host=host, port=port, sse_path=sse_path)
    server.initialize()
    server.run(transport)
