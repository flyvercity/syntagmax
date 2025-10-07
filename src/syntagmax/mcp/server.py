import logging as lg
from pathlib import Path

import click
from mcp.server.fastmcp import FastMCP

from syntagmax.artifact import ARef
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
        artifacts, _ = extract(self._config)
        self._artifacts = artifacts

    def get_requirement(self, artifact_id: str) -> str:
        artifact_id = ARef.coerce(artifact_id)

        lg.info(f'Getting requirement {artifact_id}')

        if artifact := self._artifacts.get(artifact_id):
            lg.info(f'Artifact location: {artifact.location}')
            return artifact.contents()
        else:
            return 'Theres no requirement with this ID.'


mcp = SyntagmaxMCP()


@mcp.tool()
def fetch_requirement(requirement_id: str) -> str:
    '''Get a system requirement by its ID.'''
    return mcp.get_requirement(requirement_id)


@click.group(name='mcp')
def mcp_group():
    pass


@mcp_group.command(name='run')
def run_mcp():
    lg.info('Starting MCP server')
    mcp.run()


@mcp_group.command(name='fetch-requirement')
@click.argument('requirement_id', type=str)
def fetch_requirement_cmd(requirement_id: str):
    click.echo(mcp.get_requirement(requirement_id))
