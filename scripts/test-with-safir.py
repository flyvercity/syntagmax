#!/usr/bin/env python3
# type: ignore

from pathlib import Path

import click
from duct import cmd


@click.command()
@click.option('--ai', is_flag=True)
def main(ai: bool):
    cfg = Path(__file__).parent / '../../safir/rms/rms.toml'

    args = []

    if ai:
        args.append('--ai')

    args.append('analyze')
    args.append(str(cfg))

    cmd(
        'uv',
        'run',
        'stmx',
        *args,
    ).run()


if __name__ == '__main__':
    main()
