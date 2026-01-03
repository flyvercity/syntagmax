# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Analyse a tree of artifacts.

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config


def analyse_tree(config: Config, artifacts: ArtifactMap) -> list[str]:
    errors: list[str] = []
    model = config.model

    # Check for legit types
    for a in artifacts.values():
        if not model.is_valid_atype(a.atype):
            errors.append(f'Invalid artifact type: {a}')

    # Check for a single root
    root_count = 0
    for a in artifacts.values():
        if a.atype == 'ROOT':
            root_count += 1

    if root_count != 1:
        errors.append('Must have exactly one root artifact')

    return errors
