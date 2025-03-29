''' Requirement Management System (RMS) tool. '''

import logging as lg

import click

from gitreqms.config import Config


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

        for filepath in record['filepaths']:
            lg.debug(f'Processing file: {filepath}')


if __name__ == '__main__':
    rms()
