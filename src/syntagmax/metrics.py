# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-04
# Description: Calculate metrics for a tree of artifacts.

from benedict import benedict
import polars as pl

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config
from syntagmax.render import print_metrics
from syntagmax.publish import publish_metrics


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
        print_metrics(metrics)
    elif config.metrics.output_format == 'markdown':
        publish_metrics(metrics, config.metrics.output_file)
    else:
        raise ValueError(
            f'Invalid output format: {config.metrics.output_format}'
        )
