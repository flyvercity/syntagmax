''' Requirement Management System (RMS) tool. '''

import logging as lg

import click
from git import Repo

from gitreqms.config import Config
from gitreqms.extractors.text import TextExtractor
from gitreqms.extractors.filename import FilenameExtractor
from gitreqms.extractors.obsidian import ObsidianExtractor


EXTRACTORS = {
    'text': TextExtractor,
    'filename': FilenameExtractor,
    'obsidian': ObsidianExtractor
}


@click.command(help='Requirements Management System (RMS) tool')
@click.pass_context
@click.option('--verbose', is_flag=True, help='Verbose output')
@click.argument('config', type=click.Path(exists=True))
def rms(ctx, config, verbose):
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    ctx.obj['verbose'] = verbose
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO)
    config = Config(ctx.obj)

    for record in config.input_records():
        lg.debug(f'Processing record: {record["record_base"]} ({record["driver"]})')
        repo = Repo(record['record_base'])
        extractor = EXTRACTORS[record['driver']](repo, record)
        extractor.extract()


if __name__ == '__main__':
    rms()
