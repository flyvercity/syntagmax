# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Requirement Management System (RMS) CLI tool.

import logging as lg
import sys
from pathlib import Path
import traceback

import click

import gitreqms.utils as u
from gitreqms.config import Config, Params
from gitreqms.model import StandardModel
from gitreqms.errors import RMSException
from gitreqms.extract import extract, get_available_extractors, extract_single
from gitreqms.tree import build_tree

def process(params: Params, config: Config):
    artifacts = extract(params, config)
    build_tree(artifacts)

@click.group(help='Requirements Management System (RMS) tool')
@click.pass_context
@click.option('--verbose', is_flag=True, help='Verbose output')
def rms(ctx: click.Context, verbose: bool):
    ctx.obj = Params(verbose=verbose, model=StandardModel())
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO)

@rms.command(help='Full analysis of the project')
@click.pass_obj
@click.argument('config', type=click.Path(exists=True))
def analyze(obj: Params, config: Path):
    configurator = Config(obj, config)
    process(obj, configurator)

@rms.command(help="Analyze specific file")
@click.pass_obj
@click.argument('driver', type=click.Choice(get_available_extractors()))
@click.argument('file', type=click.Path(exists=True))
def single(obj: Params, driver: str, file: Path):
    extract_single(obj, driver, file)

if __name__ == '__main__':
    try:
        rms()
    except RMSException as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        sys.exit(1)
    except Exception as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        traceback.print_exc()
        sys.exit(1)