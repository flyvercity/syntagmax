# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Builds a tree of artifacts.

import logging as lg
from typing import Sequence

from gitreqms.artifact import Artifact, ARef
from gitreqms.config import Params

def build_tree(params: Params, artifacts: Sequence[Artifact]) -> tuple[Sequence[Artifact], list[str]]:
    errors: list[str] = []
    art_map: dict[ARef, Artifact] = {a.ref(): a for a in artifacts}
    top_level = {a.ref(): a for a in artifacts if a.pids == []}
    current_level = top_level
    ansestors: set[ARef] = set()

    while True:
        found = False

        lg.debug(f'Tree level with {len(current_level)} artifacts (all {len(art_map)} artifacts)')
        for ref in current_level.keys():
            ansestors.add(ref)
            art_map.pop(ref)

        next_level: dict[ARef, Artifact] = {}

        for ref, a in art_map.items():
            for pid in a.pids:
                if pid in current_level:
                    parent = current_level[pid]
                    parent.children[ref] = a
                    next_level[ref] = a
                    found = True

        lg.debug(f'Next level with {len(next_level)} artifacts')
        current_level = next_level

        if not found:
            break

    if art_map:
        errors.extend(list(f'Orphaned artifact: {a}' for a in art_map.values()))

    for a in artifacts:
        for pid in a.pids:
            if pid not in ansestors:
                errors.append(f'Orphaned artifact: {a}')


    while True:
        found = False
        print('.')

        for a in artifacts:
            for c in a.children.values():
                if a.ref() not in c.ansestors:
                    c.ansestors.add(a.ref())
                    c.ansestors.update(a.ansestors)
                    found = True

                for ansester in a.ansestors:
                    if ansester not in c.ansestors:
                        c.ansestors.add(ansester)
                        found = True

        if not found:
            break

    for a in artifacts:
        if a.ref() in a.ansestors:
            errors.append(f'Circular reference: {a}')

    return list(top_level.values()), errors
