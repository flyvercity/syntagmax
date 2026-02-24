#!/usr/bin/env python3
# type: ignore

from pathlib import Path

from duct import cmd

cfg = Path(__file__).parent / '../../safir/rms/rms.toml'

cmd(
    'uv',
    'run',
    'stmx',
    '--verbose',
    '--render-tree',
    # '--ai',
    'analyze',
    str(cfg),
).run()
