''' Requirement Management System (RMS) tool. '''

import logging as lg
from typing import TypedDict
from pathlib import Path

import click
from git import Repo
import rich

from gitreqms.config import Config, Params
from gitreqms.extractors.text import TextExtractor
from gitreqms.extractors.filename import FilenameExtractor
from gitreqms.extractors.obsidian import ObsidianExtractor
from gitreqms.model import StandardModel
from gitreqms.artifact import Artifact


EXTRACTORS = {
    'text': TextExtractor,
    'filename': FilenameExtractor,
    'obsidian': ObsidianExtractor
}


def process(params: Params, config: Config):
    artifacts: list[Artifact] = []

    for record in config.input_records():
        lg.debug(f'Processing record: {record["record_base"]} ({record["driver"]})')
        repo = Repo(record['record_base'])
        extractor = EXTRACTORS[record['driver']](params, repo, record)
        artifacts.extend(extractor.extract())

    console = rich.get_console()
    for artifact in artifacts:
        console.print(
            f'[magenta]{artifact.driver()}[/magenta] :: '
            f'[cyan]{artifact.atype}[/cyan] :: '
            f'[green]{artifact.aid}[/green]'
            f' {artifact.metastring()}'
        )


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
@click.argument('file', type=click.Path(exists=True))
def analyze_file(obj: Params, file: Path):
    process(obj['params'], obj['config'])


if __name__ == '__main__':
    rms()
