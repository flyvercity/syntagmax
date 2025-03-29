''' Requirement Management System (RMS) tool. '''

import logging as lg

import click
from pathlib import Path
from git import Repo

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

    for artifact in artifacts:
        click.echo(f'{artifact.atype} :: {artifact.aid}')


@click.command(help='Requirements Management System (RMS) tool')
@click.pass_context
@click.option('--verbose', is_flag=True, help='Verbose output')
@click.argument('config', type=click.Path(exists=True))
def rms(ctx: click.Context, config: Path, verbose: bool):
    ctx.obj = Params(config=config, verbose=verbose, model=StandardModel())
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO)
    configurator = Config(ctx.obj)
    process(ctx.obj, configurator)


if __name__ == '__main__':
    rms()
