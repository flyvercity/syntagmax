# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Requirement Management System (RMS) CLI Tool.

import logging as lg
import sys
from pathlib import Path
import traceback

import click

import syntagmax.utils as u
from syntagmax.config import Config, Params
from syntagmax.errors import RMSException, NonFatalError
from syntagmax.extract import extract, get_available_extractors, extract_single
from syntagmax.tree import build_tree
from syntagmax.artifact import ARef
from syntagmax.render import print_arttree
from syntagmax.analyse import analyse_tree


def process(config: Config):
    errors: list[str] = []
    artifacts, e_errors = extract(config)
    errors.extend(e_errors)
    t_errors = build_tree(artifacts)
    errors.extend(t_errors)
    a_errors = analyse_tree(config, artifacts)
    errors.extend(a_errors)

    if errors:
        raise NonFatalError(errors)

    print_arttree(artifacts, ARef.root())


@click.group(help='RMS Entry Point')
@click.pass_context
@click.option('--verbose', is_flag=True, help='Verbose output')
@click.option(
    '--suppress-unexpected-children', is_flag=True, help='Suppress unexpected children type errors'
)
@click.option(
    '--suppress-required-children', is_flag=True, help='Suppress required children errors'
)
@click.option(
    '--allow-top-level-arch', is_flag=True, help='Allow top level ARCH artifacts'
)
def rms(ctx: click.Context, **kwargs):  # type: ignore
    ctx.obj = Params(**kwargs)  # type: ignore
    lg.basicConfig(level=lg.DEBUG if kwargs['verbose'] else lg.INFO)


@rms.command(help='Run full analysis of the project')
@click.pass_obj
@click.argument('config', type=click.Path(exists=True))
def analyze(obj: Params, config: Path):
    configurator = Config(obj, config)
    process(configurator)


@rms.command(help="Analyze a specific file")
@click.pass_obj
@click.argument('driver', type=click.Choice(get_available_extractors()))
@click.argument('file', type=click.Path(exists=True))
def single(obj: Params, driver: str, file: Path):
    extract_single(obj, driver, file)


def main():
    try:
        rms()

    except NonFatalError as e:
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
