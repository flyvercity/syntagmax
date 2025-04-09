# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Builds a tree of artifacts.

from gitreqms.artifact import ArtifactMap, Artifact, ARef

MAX_TREE_DEPTH = 20

class RootArtifact(Artifact):
    def __init__(self):
        super().__init__()
        self.atype = 'ROOT'
        self.aid = 'ROOT'
        self.location = 'ROOT'
        self.children = set()

def gather_ansestors(artifacts: ArtifactMap, ref: ARef, depth: int = 0) -> str | None:
    if depth > MAX_TREE_DEPTH:
        return f'Circular reference detected with {artifacts[ref].aid}'

    for child in artifacts[ref].children:
        artifacts[child].ansestors.add(ref)
        err = gather_ansestors(artifacts, child, depth + 1)

        if err:
            return err

    return None

def build_tree(artifacts: ArtifactMap) -> list[str]:
    full_set  = set(artifacts.keys())
    errors: list[str] = []

    for a in artifacts.values():
        for pid in a.pids:
            if pid not in full_set:
                errors.append(f'Missing parent: {pid} at {a}')
            else:
                artifacts[pid].children.add(a.ref())

    top_level = {a.ref(): a for a in artifacts.values() if a.pids == []}
    root = RootArtifact()

    for a in top_level.values():
        root.children.add(a.ref())

    artifacts[root.ref()] = root

    for ref in artifacts.keys():
        err = gather_ansestors(artifacts, ref)

        if err:
            errors.append(err)
            break

    return errors
