''' Requirement Management System (RMS) tool. '''

from pathlib import Path
import tomllib
import logging as lg
from typing import cast
import json
import traceback

import click
from toolz.dicttoolz import valmap
from toolz.functoolz import compose
import pyparsing as pp
from git import Repo
from git.exc import GitCommandError

from fvc.tools.rms.config import Config


@click.command(help='Requirements Management System (RMS) tool')
@click.pass_context
@click.argument('config', type=click.Path(exists=True))
def rms(ctx, config):
    ctx.obj['config'] = config
    config = Config(ctx.obj)
    return

    items = {}

    repo = Repo(config.base_dir())
    extractor = Extractor(repo)

    for file_name in config.input_file_names():
        lg.debug(f'Processing file: {file_name}')
        extractor.process_file(file_name)
        items.update({i.uid(): i for i in extractor.items()})

    deptree = build_deptree(items)
    validate(deptree)

    if ctx.obj['JSON']:
        jtree = treemap(lambda i: i.json(), deptree)
        print(json.dumps(jtree, indent=2))
