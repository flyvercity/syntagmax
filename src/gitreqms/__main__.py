# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Requirement Management System (RMS) CLI Tool.

import logging as lg
import sys
from pathlib import Path
import traceback
from typing import Sequence

import click

import gitreqms.utils as u
from gitreqms.config import Config, Params
from gitreqms.model import StandardModel
from gitreqms.errors import RMSException, NonFatalError
from gitreqms.extract import extract, get_available_extractors, extract_single
from gitreqms.tree import build_tree
from gitreqms.artifact import Artifact

def print_artifact(artifact: Artifact, level: int):
    indent = ' ' * level * 2
    u.pprint(f'{indent}[cyan]{artifact.atype}[/cyan]: [green]{artifact.aid}[/green]')

    for child in artifact.children.values():
        print_artifact(child, level + 1)

def process(params: Params, config: Config):
    errors: list[str] = []
    ex_artifacts, ex_errors = extract(params, config)
    errors.extend(ex_errors)
    b_artifacts, b_errors = build_tree(params, ex_artifacts)
    errors.extend(b_errors)

    if errors:
        raise NonFatalError(errors)
    
    u.pprint('Top Level Artifacts:')
    for a in b_artifacts:
        print_artifact(a, 0)

@click.group(help='RMS Entry Point')
@click.pass_context
@click.option('--verbose', is_flag=True, help='Verbose output')
def rms(ctx: click.Context, verbose: bool):
    ctx.obj = Params(verbose=verbose, model=StandardModel())
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO)

@rms.command(help='Run full analysis of the project')
@click.pass_obj
@click.argument('config', type=click.Path(exists=True))
def analyze(obj: Params, config: Path):
    configurator = Config(obj, config)
    process(obj, configurator)

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
        u.pprint('[light red]Non-Fatal Errors Encountered[/light red]')

        for error in e.errors:
            u.pprint(f'[red]{error}[/red]')

        sys.exit(1)

    except RMSException as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        sys.exit(2)

    except Exception as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        traceback.print_exc()
        sys.exit(3)
