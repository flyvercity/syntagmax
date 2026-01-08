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
from syntagmax.errors import RMSException, NonFatalError
from syntagmax.main import process


@click.group(help='RMS Entry Point')
@click.pass_context
@click.option(
    '--verbose', is_flag=True, help='Verbose output'
)
@click.option(
    '--render-tree', is_flag=True, help='Render the artifact tree'
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


def main():
    try:
        rms()

    except NonFatalError as e:
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
