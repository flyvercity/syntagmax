# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-03
# Description: Syntagmax Requirement Management System (RMS) Main Analysis.

import logging as lg

from syntagmax.config import Config
from syntagmax.errors import FatalError
from syntagmax.report import Report

from syntagmax.extract import extract, build_artifact_map
from syntagmax.tree import build_tree, populate_pids
from syntagmax.render import render_tree_markdown
from syntagmax.analyse import analyse_tree
from syntagmax.metrics import calculate_metrics
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
}


def public_steps():
    return [
        'extract',
        'tree',
        'impact',
        'metrics',
    ]


def process(requested_step, config: Config) -> Report:
    report = Report()
    errors: list = []
    artifacts_list = None
    artifacts = None
    plan = get_execution_plan(DEPS, requested_step)

    for step in plan:
        if step == 'populate_revisions' and config.params.get('no_git', False):
            lg.info(f'Skipping step: {step} (--no-git flag is set)')
            continue

        lg.info(f'Executing step: {step}')

        match step:
            case 'extract':
                artifacts_list = extract(config, errors)
            case 'build_artifact_map':
                if artifacts_list is None:
                    raise FatalError(f'Artifacts list not initialized for step {step}')
                artifacts = build_artifact_map(artifacts_list, errors)
            case 'metrics':
                if artifacts is None:
                    raise FatalError(f'Artifacts not initialized for step {step}')
                report.metrics = calculate_metrics(config, artifacts, errors)

                req_type = config.metrics.requirement_type
                contributing_records = set()
                for a in artifacts.values():
                    if a.atype == req_type and a.record:
                        contributing_records.add(a.record.name)

                if len(contributing_records) > 1:
                    report.metrics_by_input = []
                    for record_name in sorted(contributing_records):
                        per_input_metrics = calculate_metrics(config, artifacts, errors, filter_record_name=record_name)
                        if per_input_metrics:  # skip if no reqs in this input
                            report.metrics_by_input.append((record_name, per_input_metrics))
            case 'impact':
                if artifacts is None:
                    raise FatalError(f'Artifacts not initialized for step {step}')
                report.impact = perform_impact_analysis(config, artifacts, errors)
                # Task generation is an internal post-processing phase of impact
                if config.impact.tasks_enabled:
                    from syntagmax.tasks import generate_tasks

                    report.tasks_summary = generate_tasks(config, artifacts, errors, report.impact)
            case _:
                if artifacts is None:
                    raise FatalError(f'Artifacts not initialized for step {step}')
                STEPS[step](config, artifacts, errors)

    if config.params['render_tree']:
        if artifacts and 'ROOT' in artifacts:
            report.tree_text = render_tree_markdown(artifacts)

    report.errors = errors
    report.report_config = config.report
    return report
