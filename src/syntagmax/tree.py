# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Builds a tree of artifacts.

import logging as lg

from syntagmax.config import Config
from syntagmax.artifact import ArtifactMap, Artifact, Location, ParentLink

MAX_TREE_DEPTH = 20


class RootLocation(Location):
    def __str__(self):
        return '<ROOT>'


class RootArtifact(Artifact):
    def __init__(self, config: Config):
        super().__init__(config)
        self.atype = 'ROOT'
        self.aid = 'ROOT'
        self.location = RootLocation()
        self.children = set()


def populate_pids(config: Config, artifacts: ArtifactMap):
    if not config.metamodel:
        return

    for a in artifacts.values():
        if a.atype not in config.metamodel['artifacts']:
            continue

        rules = config.metamodel['artifacts'][a.atype]['attributes']
        for attr_name, rule in rules.items():
            type_info = rule.get('type_info', {})
            if type_info.get('type') == 'reference' and type_info.get('to_parent'):
                val = a.fields.get(attr_name)
                if not val:
                    continue

                refs = val if rule.get('multiple') else [val]
                for ref_str in refs:
                    try:
                        parts = ref_str.split('@')
                        aid = parts[0]
                        nominal_revision = parts[1] if len(parts) > 1 else None

                        parent_artifact = artifacts.get(aid)
                        if parent_artifact:
                            # Find trace mode from a.atype to parent_artifact.atype
                            trace_mode = config.get_trace_mode(a.atype, parent_artifact.atype)
                            if trace_mode == 'timestamp' and not nominal_revision:
                                nominal_revision = 'older'

                        a.parent_links.append(ParentLink(pid=aid, nominal_revision=nominal_revision))

                        if aid not in a.pids:
                            a.pids.append(aid)
                    except Exception as e:
                        lg.warning(f"Error processing parent link '{ref_str}' for artifact '{a.aid}': {e}")


def gather_ansestors(artifacts: ArtifactMap, ref: str, depth: int = 0) -> str | None:
    if depth > MAX_TREE_DEPTH:
        return f'Circular reference detected with {artifacts[ref].aid}'

    for child in artifacts[ref].children:
        artifacts[child].ansestors.add(ref)
        err = gather_ansestors(artifacts, child, depth + 1)

        if err:
            return err

    return None


def build_tree(config: Config, artifacts: ArtifactMap) -> list[str]:
    full_set = set(artifacts.keys())
    errors: list[str] = []

    for a in artifacts.values():
        for pid in a.pids:
            if pid not in full_set:
                errors.append(f'Missing parent: {pid} at {a}')
            else:
                artifacts[pid].children.add(a.aid)

    top_level = {a.aid: a for a in artifacts.values() if a.pids == []}
    root = RootArtifact(config)

    for a in top_level.values():
        root.children.add(a.aid)

    artifacts[root.aid] = root

    for ref in artifacts.keys():
        err = gather_ansestors(artifacts, ref)

        if err:
            errors.append(err)
            break

    return errors
