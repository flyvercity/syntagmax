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
from importlib.metadata import version

import click
from rich.logging import RichHandler

import syntagmax.utils as u
from syntagmax.config import Config, Params
from syntagmax.errors import RMSException, FatalError
from syntagmax.main import process, public_steps
from syntagmax.init_cmd import init_project
from syntagmax.cli_publish import publish
from syntagmax.cli_change import change
from syntagmax.cli_edit import edit
from syntagmax.cli_tools import trace, mcp, schema, ci


@click.group(help='RMS Entry Point')
@click.version_option(version('syntagmax'))
@click.pass_context
@click.option('--verbose', is_flag=True, help='Verbose output')
@click.option('--render-tree', is_flag=True, help='Render the artifact tree')
@click.option('--cwd', type=click.Path(exists=True), help='Change the working directory')
@click.option('--no-git', is_flag=True, help='Skip git history extraction')
@click.option('--output', default='.syntagmax/reports/report.md', help='Report output file (default: .syntagmax/reports/report.md)')
@click.option('--lang', 'language', type=click.Choice(['en', 'ru']), default=None, help='Output language (en, ru)')
def rms(ctx: click.Context, **kwargs: dict[str, Any]):
    verbose = kwargs['verbose']
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO, handlers=[RichHandler()])
    ctx.obj = Params(**kwargs)  # type: ignore

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
    type=click.Path(),
    default='.syntagmax/config.toml',
)
@click.option('--allow-dirty-worktree', is_flag=True, help='Allow analysis on a dirty git worktree')
@click.option('--suppress-tracing', is_flag=True, help='Suppress tracing model errors')
@click.argument('step', type=click.Choice(public_steps()), default='metrics')
def analyze(obj: Params, config_file: Path, allow_dirty_worktree: bool, suppress_tracing: bool, step: str):
    import sys

    cfg_path = Path(config_file)
    if not cfg_path.exists():
        u.pprint(f'[red]Error: Configuration file "{cfg_path}" does not exist.[/red]')
        sys.exit(1)
    obj['allow_dirty_worktree'] = allow_dirty_worktree
    obj['suppress_tracing'] = suppress_tracing
    config = Config(obj, cfg_path)
    report = process(step, config)

    output = obj['output']
    markdown = report.render()

    if output == 'console':
        print(markdown)
    else:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding='utf-8')

    error_count = len(report.errors)
    if output != 'console':
        summary = f'Report written to {output}'
        if error_count:
            summary += f', {error_count} error(s) found'
        color = 'yellow' if error_count else 'green'
        u.pprint(f'[{color}]{summary}[/{color}]')


rms.add_command(publish)
rms.add_command(change)
rms.add_command(trace)
rms.add_command(edit)
rms.add_command(mcp)
rms.add_command(schema)
rms.add_command(ci)


def main():
    try:
        rms()

    except FatalError as e:
        u.pprint(f'[red]{len(e.errors)} fatal error(s): {e.errors[0]}[/red]')
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
