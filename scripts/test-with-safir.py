#!/usr/bin/env python3
# type: ignore

from pathlib import Path

import click
from duct import cmd, StatusError
import rich


@click.command()
@click.option('--ai', is_flag=True)
@click.option('--verbose', is_flag=True)
def main(ai: bool, verbose: bool):
    cfg = Path(__file__).parent / '../../safir/rms/rms.toml'

    args = []

    if verbose:
        args.append('--verbose')

    if ai:
        args.append('--ai')

    args.append('--render-tree')
    args.append('analyze')
    args.append(str(cfg))

    try:
        cmd(
            'uv',
            'run',
            'syntagmax',
            *args,
        ).run()

    except StatusError:
        rich.print('[bold red]Command failed[/bold red]')


if __name__ == '__main__':
    main()
