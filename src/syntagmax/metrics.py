# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-04
# Description: Calculate metrics for a tree of artifacts.

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config

from benedict import benedict


def calculate_metrics(config: Config, artifacts: ArtifactMap) -> benedict:
    metrics = benedict()
    metrics['total_artifacts'] = len(artifacts)
    return metrics
