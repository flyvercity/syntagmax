# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-03
# Description: Syntagmax Requirement Management System (RMS) Main Analysis.

import logging as lg

from syntagmax.config import Config
from syntagmax.errors import FatalError

from syntagmax.extract import extract, build_artifact_map
from syntagmax.tree import build_tree, populate_pids
from syntagmax.render import print_arttree
from syntagmax.analyse import analyse_tree
from syntagmax.metrics import calculate_metrics
from syntagmax.ai import ai_analyze
from syntagmax.git_utils import populate_revisions
from syntagmax.utils import get_execution_plan
from syntagmax.impact import perform_impact_analysis


STEPS = {
    'extract': extract,
    'build_artifact_map': build_artifact_map,
    'populate_pids': populate_pids,
    'build_tree': build_tree,
    'tree': analyse_tree,
    'populate_revisions': populate_revisions,
    'impact': perform_impact_analysis,
    'metrics': calculate_metrics,
    'ai': ai_analyze,
}

DEPS = {
    'extract': set(),
    'build_artifact_map': {'extract'},
    'populate_pids': {'build_artifact_map'},
    'build_tree': {'populate_pids'},
    'tree': {'build_tree'},
    'populate_revisions': {'build_artifact_map'},
    'impact': {'populate_revisions', 'build_tree'},
    'metrics': {'tree'},
    'ai': {'build_artifact_map'},
}


def public_steps():
    return [
        'extract',
        'tree',
        'impact',
        'metrics',
        'ai',
    ]


def process(requested_step, config: Config):
    errors: list[str] = []
    artifacts_list = None
    artifacts = None
    plan = get_execution_plan(DEPS, requested_step)

    for step in plan:
        lg.info(f'Executing step: {step}')

        match step:
            case 'extract':
                artifacts_list = extract(config, errors)
            case 'build_artifact_map':
                if artifacts_list is None:
                    raise FatalError(f'Artifacts list not initialized for step {step}')

                artifacts = build_artifact_map(artifacts_list, errors)
            case _:
                if artifacts is None:
                    raise FatalError(f'Artifacts not initialized for step {step}')

                STEPS[step](config, artifacts, errors)

    if config.params['render_tree']:
        if not artifacts or 'ROOT' not in artifacts:
            lg.warning('No tree was built, skipping tree rendering')
        else:
            print_arttree(artifacts, 'ROOT', verbose=config.params['verbose'])

    if errors:
        raise FatalError(errors)
