# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Builds a tree of artifacts.

from typing import Sequence

from gitreqms.artifact import Artifact
from gitreqms.model import IModel
from gitreqms.errors import NonFatalError

def build_tree(artifacts: Sequence[Artifact], model: IModel) -> Sequence[Artifact]:
    errors: list[str] = []

    for a in artifacts:
        if not model.isValidAType(a.atype):
            errors.append(f'Invalid artifact type: {a.atype} at {a.location}')

    top_level = [a for a in artifacts if a.pids == []]

    if errors:
        raise NonFatalError(errors)

    return top_level
