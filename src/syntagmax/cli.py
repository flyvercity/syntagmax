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
from syntagmax.main import process, public_steps
from syntagmax.mcp.server import run_mcp_server
from syntagmax.init_cmd import init_project
from syntagmax.edit import renumber_artifacts


_error_output = 'errors.md'


@click.group(help='RMS Entry Point')
@click.pass_context
@click.option('--verbose', is_flag=True, help='Verbose output')
@click.option('--render-tree', is_flag=True, help='Render the artifact tree')
@click.option('--cwd', type=click.Path(exists=True), help='Change the working directory')
@click.option('--no-git', is_flag=True, help='Skip git history extraction')
@click.option('--error-output', default='errors.md', help='Error report output file (default: errors.md)')
def rms(ctx: click.Context, **kwargs: dict[str, Any]):
    global _error_output

    verbose = kwargs['verbose']
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO, handlers=[RichHandler()])
    ctx.obj = Params(**kwargs)  # type: ignore
    _error_output = ctx.obj['error_output']

    if ctx.obj['cwd']:
        lg.info(f'Changing working directory to: {ctx.obj["cwd"]}')
        os.chdir(ctx.obj['cwd'])

    lg.info(f'Verbose: {verbose}')


@rms.command(help='Initialize a new Syntagmax project')
@click.pass_context
def init(ctx: click.Context):
    cwd = ctx.obj.get('cwd') if ctx.obj else None
    init_project(cwd)
    u.pprint('[green]Initialized a new Syntagmax project.[/green]')


@rms.command(help='Run full analysis of the project')
@click.pass_obj
@click.option(
    '-f',
    '--config-file',
    type=click.Path(exists=True),
    default='.syntagmax/config.toml',
)
@click.option('--allow-dirty-worktree', is_flag=True, help='Allow analysis on a dirty git worktree')
@click.option('--suppress-tracing', is_flag=True, help='Suppress tracing model errors')
@click.argument('step', type=click.Choice(public_steps()), default='metrics')
def analyze(obj: Params, config_file: Path, allow_dirty_worktree: bool, suppress_tracing: bool, step: str):
    obj['allow_dirty_worktree'] = allow_dirty_worktree
    obj['suppress_tracing'] = suppress_tracing
    config = Config(obj, config_file)
    process(step, config)


@rms.group(help='Project Editing Commands')
def edit():
    pass


@edit.command(help='Renumber artifact IDs')
@click.pass_obj
@click.argument(
    'config_path',
    type=click.Path(exists=True),
    default='.syntagmax/config.toml',
)
@click.option('--all', 'renumber_all', is_flag=True, help='Renumber all artifacts')
@click.option('--atype', help='Filter by artifact type')
@click.option('--schema', help='Custom ID schema')
@click.option('--dry-run', is_flag=True, help='Perform a dry run without modifications')
def renumber(obj: Params, config_path: Path, renumber_all: bool, atype: str | None, schema: str | None, dry_run: bool):
    if not renumber_all and not atype:
        u.pprint('[red]Either --all or --atype must be specified.[/red]')
        return

    configurator = Config(obj, Path(config_path))
    renumber_artifacts(configurator, atype, schema, dry_run)


@rms.group(help='MCP Server Management')
def mcp():
    pass


@mcp.command(help='Run the MCP server')
@click.pass_obj
@click.argument('config_path', type=click.Path(exists=True))
@click.option('--host', default='127.0.0.1', help='Host for SSE')
@click.option('--port', default=8000, help='Port for SSE')
@click.option('--sse-path', default='/', help='Path for SSE stream')
@click.option('--transport', default='stdio', type=click.Choice(['stdio', 'sse']), help='MCP transport to use')
def run(obj: Params, config_path: str, host: str, port: int, sse_path: str, transport: str):
    configurator = Config(obj, Path(config_path))
    run_mcp_server(configurator, host, port, sse_path, transport)


def _write_error_report(errors: list[str], output_file: str):
    lines = ['# Error Report', '', f'Total errors: {len(errors)}', '']
    for i, error in enumerate(errors, 1):
        lines.append(f'{i}. {error}')
    lines.append('')
    Path(output_file).write_text('\n'.join(lines), encoding='utf-8')


def main():
    try:
        rms()

    except FatalError as e:
        _write_error_report(e.errors, _error_output)
        u.pprint(f'[red]{len(e.errors)} error(s) found. See {_error_output} for details.[/red]')
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
