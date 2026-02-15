# Author: Boris Resnick
# Created: 2026-02-15
# Description: Publishes the project metrics to a file.

from pathlib import Path
import logging as lg

import rich
from benedict import benedict


def publish_metrics(
    metrics: benedict, output: str
):
    markdown = '# Project Metrics\n\n'

    for k, v in metrics.items():
        markdown += f'{k}: {v}  \n'

    if output == 'console':
        rich.print(markdown)
    else:
        output_file = Path(output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        lg.info(f'Writing metrics to {output_file}')
        output_file.write_text(markdown, encoding='utf-8')
