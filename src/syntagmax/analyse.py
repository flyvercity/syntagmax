# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Analyse a tree of artifacts.

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config


def analyse_tree(config: Config, artifacts: ArtifactMap) -> list[str]:
    errors: list[str] = []
    errors.extend(check_single_root(artifacts))
    errors.extend(check_legit_types(config, artifacts))
    return errors


def check_single_root(artifacts: ArtifactMap) -> list[str]:
    errors: list[str] = []
    root_count = 0
    for a in artifacts.values():
        if a.atype == 'ROOT':
            root_count += 1

    if root_count != 1:
        errors.append('Must have exactly one root artifact')

    return errors


def check_legit_types(config: Config, artifacts: ArtifactMap) -> list[str]:
    model = config.model
    errors: list[str] = []

    for a in artifacts.values():
        if not model.is_valid_atype(a.atype):
            errors.append(f'Invalid artifact type: {a}')

    return errors
