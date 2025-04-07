# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Builds a tree of artifacts.

from gitreqms.artifact import ArtifactMap, Artifact
from gitreqms.config import Params


class RootArtifact(Artifact):
    def __init__(self):
        super().__init__(atype='ROOT', aid='ROOT', location='ROOT')
        self.children = set()


def build_tree(params: Params, artifacts: ArtifactMap) -> tuple[RootArtifact, list[str]]:
    full_set  = set(artifacts.keys())
    errors: list[str] = []

    for a in artifacts.values():
        for pid in a.pids:
            if pid not in full_set:
                errors.append(f'Missing parent: {pid}')
            else:
                artifacts[pid].children.add(a.ref())

    top_level = {a.ref(): a for a in artifacts.values() if a.pids == []}
    root = RootArtifact()

    for a in top_level.values():
        root.children.add(a.ref())

    return root, errors
