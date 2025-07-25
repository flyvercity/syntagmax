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

    # Check for allowed children
    if not config.params['suppress_unexpected_children']:
        for a in artifacts.values():
            for c in a.children:
                if not model.allowed_child(a.atype, c.atype):
                    errors.append(f'Invalid child {c.atype} for {a} at {artifacts[c]}')

    # Check for required children
    if not config.params['suppress_required_children']:
        for a in artifacts.values():
            for c in model.required_children(a.atype):
                if c not in map(lambda c: c.atype, a.children):
                    errors.append(f'Required child {c} not found for {a}')
        
    return errors
