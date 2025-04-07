# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Requirement Management System (RMS) CLI Tool.

import logging as lg
import sys
from pathlib import Path
import traceback

import click

import gitreqms.utils as u
from gitreqms.config import Config, Params
from gitreqms.errors import RMSException, NonFatalError
from gitreqms.extract import extract, get_available_extractors, extract_single
from gitreqms.tree import build_tree
from gitreqms.artifact import ARef
from gitreqms.render import print_arttree
from gitreqms.analyse import analyse_tree

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
    
    u.pprint('Top Level Artifacts:')
    print_arttree(artifacts, ARef.root())

@click.group(help='RMS Entry Point')
@click.pass_context
@click.option('--verbose', is_flag=True, help='Verbose output')
@click.option('--suppress-unexpected-children', is_flag=True, help='Suppress unexpected children type errors')
@click.option('--suppress-required-children', is_flag=True, help='Suppress required children errors')
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

if __name__ == '__main__':
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
