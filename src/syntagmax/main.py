# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-03
# Description: Syntagmax Requirement Management System (RMS) Main Analysis.

import logging as lg

from syntagmax.config import Config
from syntagmax.errors import FatalError

from syntagmax.extract import extract
from syntagmax.tree import build_tree
from syntagmax.artifact import ARef
from syntagmax.render import print_arttree
from syntagmax.analyse import analyse_tree
from syntagmax.metrics import render_metrics
from syntagmax.ai import ai_analyze


def process(config: Config):
    errors: list[str] = []
    artifacts, e_errors = extract(config)
    errors.extend(e_errors)
    t_errors = build_tree(config, artifacts)
    errors.extend(t_errors)
    a_errors = analyse_tree(config, artifacts)
    errors.extend(a_errors)

    if errors:
        raise FatalError(errors)

    if not artifacts:
        lg.warning('No artifacts found')
        return

    if config.params['render_tree']:
        print_arttree(artifacts, ARef.root(), verbose=config.params['verbose'])

    if config.metrics.enabled:
        render_metrics(config, artifacts)

    if config.params['ai']:
        ai_analyze(config, artifacts)
