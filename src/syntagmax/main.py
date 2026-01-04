# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-03
# Description: Syntagmax Requirement Management System (RMS) Main Analysis.
import logging as lg

import rich
from rich.table import Table

from syntagmax.config import Config
from syntagmax.errors import NonFatalError

from syntagmax.extract import extract
from syntagmax.tree import build_tree
from syntagmax.artifact import ARef
from syntagmax.render import print_arttree
from syntagmax.analyse import analyse_tree
from syntagmax.metrics import calculate_metrics


def process(config: Config):
    errors: list[str] = []
    artifacts, e_errors = extract(config)
    errors.extend(e_errors)
    t_errors = build_tree(config, artifacts)
    errors.extend(t_errors)
    a_errors = analyse_tree(config, artifacts)
    errors.extend(a_errors)

    if errors:
        raise NonFatalError(errors)

    if not artifacts:
        lg.warning('No artifacts found')
        return

    print_arttree(artifacts, ARef.root(), verbose=config.params['verbose'])
    metrics = calculate_metrics(config, artifacts)

    table = Table(title="Artifact Metrics")

    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    for k, v in metrics.items():
        table.add_row(str(k), str(v))

    rich.print(table)
