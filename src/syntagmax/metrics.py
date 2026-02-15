# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-04
# Description: Calculate metrics for a tree of artifacts.

from pathlib import Path
import rich
from rich.table import Table
from benedict import benedict
import polars as pl

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config


def calculate_metrics(config: Config, artifacts: ArtifactMap) -> benedict:
    metrics = benedict()

    df = pl.DataFrame([{
        'atype': artifact.atype,
        'aid': artifact.aid,
        'status': artifact.fields.get(config.metrics.status_field, 'UNKNOWN'),
        'verify': artifact.fields.get(config.metrics.verify_field),
        'has_tbd': any(
            config.metrics.tbd_marker in field for field in artifact.fields.values()
        ),
    } for artifact in artifacts.values()])

    requirements = (
        df.filter(pl.col('atype') == config.metrics.requirement_type)  # type: ignore
    )

    req_count = requirements.height
    metrics['total_requirements'] = req_count

    metrics['requirements_by_status'] = (
        requirements.group_by('status')  # type: ignore
        .agg(pl.count())
        .sort('status')
        .to_dicts()
    )
    metrics['requirements_without_verify_pct'] = (
        requirements.filter(  # type: ignore
            pl.col('verify')
            .is_null()
        ).height / float(req_count) * 100.0
    )
    metrics['requirements_with_tbd_pct'] = (
        requirements.filter(  # type: ignore
            pl.col('has_tbd')
        ).height / float(req_count) * 100.0
    )

    return metrics


def render_metrics(config: Config, artifacts: ArtifactMap):
    metrics = calculate_metrics(config, artifacts)

    if config.metrics.output_format == 'rich':
        render_metrics_rich(metrics)
    elif config.metrics.output_format == 'markdown':
        markdown = render_metrics_markdown(metrics)

        if config.metrics.output_file == 'console':
            rich.print(markdown)
        elif config.metrics.output_file:
            output_file = Path(config.metrics.output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(markdown, encoding='utf-8')
    else:
        raise ValueError(
            f'Invalid output format: {config.metrics.output_format}'
        )


def render_metrics_markdown(metrics: benedict):
    markdown = '# Project Metrics\n\n'

    for k, v in metrics.items():
        markdown += f'{k}: {v}  \n'

    return markdown


def render_metrics_rich(metrics: benedict):
    table = Table(title="Artifact Metrics")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    for k, v in metrics.items():
        table.add_row(str(k), str(v))

    rich.print(table)
