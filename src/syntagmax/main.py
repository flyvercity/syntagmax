# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-03
# Description: Syntagmax Requirement Management System (RMS) Main Analysis.

import logging as lg

from syntagmax.config import Config
from syntagmax.errors import FatalError

from syntagmax.extract import extract
from syntagmax.tree import build_tree, populate_pids
from syntagmax.render import print_arttree
from syntagmax.analyse import analyse_tree
from syntagmax.metrics import calculate_metrics, render_metrics
from syntagmax.ai import ai_analyze
from syntagmax.git_utils import populate_revisions
from syntagmax.impact import perform_impact_analysis, render_impact_report


def process(config: Config):
    errors: list[str] = []
    artifacts, e_errors = extract(config)
    errors.extend(e_errors)
    populate_pids(config, artifacts)
    t_errors = build_tree(config, artifacts)
    errors.extend(t_errors)
    a_errors = analyse_tree(config, artifacts)
    errors.extend(a_errors)

    if not artifacts:
        lg.warning('No artifacts found')
        return

    if not config.params.get('no_git', False):
        try:
            populate_revisions(config, artifacts)
        except Exception as e:
            lg.warning(f"Failed to extract git revisions: {e}")
    else:
        lg.warning("Git history extraction skipped (--no-git)")

    # Impact analysis
    impact_data = None
    if config.impact.enabled:
        impact_data = perform_impact_analysis(config, artifacts, errors)

    if config.params['render_tree']:
        print_arttree(artifacts, 'ROOT', verbose=config.params['verbose'])

    if errors:
        raise FatalError(errors)

    if config.metrics.enabled:
        metrics = calculate_metrics(config, artifacts, errors)

        if errors:
            raise FatalError(errors)

        render_metrics(metrics, config)

    if impact_data:
        render_impact_report(impact_data, config)

    if config.params['ai']:
        ai_analyze(config, artifacts)
