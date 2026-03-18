# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Syntagmax Requirement Management System (RMS) CLI Tool.

import logging as lg
import sys
import traceback
from pathlib import Path
from typing import Any

import click
from rich.logging import RichHandler

import syntagmax.utils as u
from syntagmax.config import Config, Params
from syntagmax.errors import RMSException, FatalError
from syntagmax.main import process
from syntagmax.mcp.server import run_mcp_server


@click.group(help='RMS Entry Point')
@click.pass_context
@click.option(
    '--verbose', is_flag=True, help='Verbose output'
)
@click.option(
    '--render-tree', is_flag=True, help='Render the artifact tree'
)
@click.option(
    '--ai', is_flag=True, help='Use AI to analyze the project'
)
def rms(ctx: click.Context, **kwargs: dict[str, Any]):
    verbose = kwargs['verbose']
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO, handlers=[RichHandler()])
    ctx.obj = Params(**kwargs)  # type: ignore
    lg.info(f'Verbose: {verbose}')


@rms.command(help='Run full analysis of the project')
@click.pass_obj
@click.argument('config', type=click.Path(exists=True))
def analyze(obj: Params, config: Path):
    configurator = Config(obj, config)
    process(configurator)


@rms.group(help='MCP Server Management')
def mcp():
    pass


@mcp.command(help='Run the MCP server')
@click.pass_obj
@click.argument('config_path', type=click.Path(exists=True))
@click.option('--transport', type=click.Choice(['sse', 'stdio']), default='sse', help='Transport layer')
@click.option('--host', default='127.0.0.1', help='Host for SSE')
@click.option('--port', default=8000, help='Port for SSE')
def run(obj: Params, config_path: str, transport: str, host: str, port: int):
    configurator = Config(obj, Path(config_path))
    run_mcp_server(configurator, transport, host, port)


def main():
    try:
        rms()

    except FatalError as e:
        for error in e.errors:
            u.pprint(f'[red]{error}[/red]')

        u.pprint(
            '[light red]'
            f'Non-Fatal Errors Encountered: {len(e.errors)}'
            '[/light red]'
        )

        sys.exit(1)

    except RMSException as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        sys.exit(2)

    except Exception as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        traceback.print_exc()
        sys.exit(3)


if __name__ == '__main__':
    main()
