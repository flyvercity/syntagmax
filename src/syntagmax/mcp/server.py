import logging as lg
from pathlib import Path

import click
from mcp.server.fastmcp import FastMCP

from syntagmax.config import Config, Params
from syntagmax.extract import extract


CONFIG_FILENAME = Path('C:\\Users\\boris\\projects\\flyvercity\\safir\\safir-fusion-rms\\rms.toml')


class SyntagmaxMCP(FastMCP):
    def __init__(self):
        super().__init__('System Requirements Source')

        params = Params(
            verbose=False,
            suppress_unexpected_children=False,
            suppress_required_children=False,
            allow_top_level_arch=False
        )

        self._config = Config(params, CONFIG_FILENAME)
        self._artifacts = extract(self._config)


mcp = SyntagmaxMCP()


@mcp.tool()
def fetch_requirement(requirement_id: str) -> str:
    '''Get a system requirement by ID.'''
    return f'Requirement {requirement_id}'


@click.command(name='mcp')
def mcp_cmd():
    lg.info('Starting MCP server')
    mcp.run()
