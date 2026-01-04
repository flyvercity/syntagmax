# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-04
# Description: Calculate metrics for a tree of artifacts.

import rich
from rich.table import Table
from benedict import benedict

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config


def calculate_metrics(config: Config, artifacts: ArtifactMap) -> benedict:
    metrics = benedict()
    metrics['total_artifacts'] = len(artifacts)
    return metrics


def render_metrics(config: Config, artifacts: ArtifactMap):
    metrics = calculate_metrics(config, artifacts)

    table = Table(title="Artifact Metrics")

    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    for k, v in metrics.items():
        table.add_row(str(k), str(v))

    rich.print(table)
