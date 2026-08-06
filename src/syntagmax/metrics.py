# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-04
# Description: Calculate metrics for a tree of artifacts.

from benedict import benedict
import polars as pl

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config
from syntagmax.i18n import _
from syntagmax.report import ReportError, CAT_STRUCTURE


def calculate_metrics(config: Config, artifacts: ArtifactMap, errors: list, filter_record_name: str | None = None) -> benedict:
    metrics = benedict()

    source_artifacts = artifacts.values()
    if filter_record_name is not None:
        source_artifacts = [a for a in source_artifacts if a.record and a.record.name == filter_record_name]

    df = pl.DataFrame(
        [
            {
                'atype': artifact.atype,
                'aid': artifact.aid,
                'status': artifact.fields.get(config.metrics.status_field, 'UNKNOWN'),
                'verify': artifact.fields.get(config.metrics.verify_field),
                'has_tbd': any(
                    config.metrics.tbd_marker in str(item) for field in artifact.fields.values() for item in (field if isinstance(field, list) else [field])
                ),
            }
            for artifact in source_artifacts
        ]
    )

    requirements = (
        df.filter(pl.col('atype') == config.metrics.requirement_type)  # type: ignore
    )

    req_count = requirements.height

    if req_count == 0:
        errors.append(ReportError(message=_('Metrics: No requirements found'), category=CAT_STRUCTURE))
        return metrics

    metrics['total_requirements'] = req_count

    metrics['requirements_by_status'] = (
        requirements.group_by('status')  # type: ignore
        .agg(pl.count())
        .sort('status')
        .to_dicts()
    )
    metrics['requirements_without_verify_pct'] = (
        requirements.filter(  # type: ignore
            pl.col('verify').is_null()
        ).height
        / float(req_count)
        * 100.0
    )
    metrics['requirements_with_tbd_pct'] = (
        requirements.filter(  # type: ignore
            pl.col('has_tbd')
        ).height
        / float(req_count)
        * 100.0
    )

    return metrics
