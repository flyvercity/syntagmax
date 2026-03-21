# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Syntagmax Requirement Management System (RMS) CLI Tool.

import logging as lg
import sys
import os
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
@click.option('--verbose', is_flag=True, help='Verbose output')
@click.option('--render-tree', is_flag=True, help='Render the artifact tree')
@click.option('--ai', is_flag=True, help='Use AI to analyze the project')
@click.option('--cwd', type=click.Path(exists=True), help='Change the working directory')
@click.option('--no-git', is_flag=True, help='Skip git history extraction')
def rms(ctx: click.Context, **kwargs: dict[str, Any]):

    verbose = kwargs['verbose']
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO, handlers=[RichHandler()])
    ctx.obj = Params(**kwargs)  # type: ignore

    if ctx.obj['cwd']:
        lg.info(f'Changing working directory to: {ctx.obj["cwd"]}')
        os.chdir(ctx.obj['cwd'])

    lg.info(f'Verbose: {verbose}')


@rms.command(help='Run full analysis of the project')
@click.pass_obj
@click.argument(
    'config',
    type=click.Path(exists=True),
    default='.syntagmax/config.toml',
)
@click.option('--allow-dirty-worktree', is_flag=True, help='Allow analysis on a dirty git worktree')
def analyze(obj: Params, config: Path, allow_dirty_worktree: bool):
    obj['allow_dirty_worktree'] = allow_dirty_worktree
    configurator = Config(obj, config)
    process(configurator)


@rms.group(help='MCP Server Management')
def mcp():
    pass


@mcp.command(help='Run the MCP server')
@click.pass_obj
@click.argument('config_path', type=click.Path(exists=True))
@click.option('--host', default='127.0.0.1', help='Host for SSE')
@click.option('--port', default=8000, help='Port for SSE')
@click.option('--sse-path', default='/', help='Path for SSE stream')
def run(obj: Params, config_path: str, host: str, port: int, sse_path: str):
    configurator = Config(obj, Path(config_path))
    run_mcp_server(configurator, host, port, sse_path)


def main():
    try:
        rms()

    except FatalError as e:
        for error in e.errors:
            u.pprint(f'[red]{error}[/red]')

        u.pprint(f'[light red]Non-Fatal Errors Encountered: {len(e.errors)}[/light red]')

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
