''' Requirement Management System (RMS) CLI tool. '''

import logging as lg
import sys
from typing import cast, Sequence
from pathlib import Path
import traceback

import click
from rich.console import Console

from gitreqms.config import Config, Params
from gitreqms.extractors.text import TextExtractor
from gitreqms.extractors.filename import FilenameExtractor
from gitreqms.extractors.obsidian import ObsidianExtractor
from gitreqms.model import StandardModel
from gitreqms.artifact import Artifact
from gitreqms.errors import RMSException


class NonFatalError(RMSException):
    def __init__(self):
        super().__init__('Errors were reported')


EXTRACTORS = {
    'text': TextExtractor,
    'filename': FilenameExtractor,
    'obsidian': ObsidianExtractor
}


console = Console()


def pprint(what: str):
    console.print(what)  # type: ignore


def print_artifacts(artifacts: Sequence[Artifact]):
    for artifact in artifacts:
        pprint(
            f'[magenta]{artifact.driver()}[/magenta] :: '
            f'[cyan]{artifact.atype}[/cyan] :: '
            f'[green]{artifact.aid}[/green]'
            f' {artifact.metastring()}'
        )


def process(params: Params, config: Config):
    artifacts: Sequence[Artifact] = []
    errors: Sequence[str] = []

    for record in config.input_records():
        lg.debug(f'Processing record: {record["record_base"]} ({record["driver"]})')
        extractor = EXTRACTORS[record['driver']](params)
        record_artifacts, record_errors = extractor.extract(record)
        artifacts.extend(record_artifacts)
        errors.extend(record_errors)

    for error in errors:
        pprint(f'[red]{error}[/red]')

    if errors:
        raise NonFatalError()
    else:
        print_artifacts(artifacts)


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
@click.argument('driver', type=click.Choice(cast(Sequence[str], EXTRACTORS.keys())))
@click.argument('file', type=click.Path(exists=True))
def single(obj: Params, driver: str, file: Path):
    extractor = EXTRACTORS[driver](obj)
    artifacts, errors = extractor.extract_from_file(Path(file))

    print_artifacts(artifacts)

    for error in errors:
        pprint(f'[red]{error}[/red]')

    if errors:
        raise NonFatalError()


if __name__ == '__main__':
    try:
        rms()
    except RMSException as e:
        pprint(f'[red]Failed: {e}[/red]')
        sys.exit(1)
    except Exception as e:
        pprint(f'[red]Failed: {e}[/red]')
        traceback.print_exc()
        sys.exit(1)
