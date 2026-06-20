# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-03-21
# Description: Impact analysis for a tree of artifacts.

import logging as lg

from benedict import benedict

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config


def perform_impact_analysis(config: Config, artifacts: ArtifactMap, errors: list[str]) -> benedict:

    impact_data = benedict()
    suspicious_links = []

    for a in artifacts.values():
        if a.atype == 'ROOT':
            continue

        for link in a.parent_links:
            parent = artifacts.get(link.pid)
            if not parent:
                continue

            # Impact analysis logic
            if link.nominal_revision == 'older':
                # via timestamp
                if a.latest_revision and parent.latest_revision:
                    if parent.latest_revision.timestamp > a.latest_revision.timestamp:
                        link.is_suspicious = True
            elif link.nominal_revision:
                # via commit
                if parent.latest_revision:
                    if (
                        link.nominal_revision != parent.latest_revision.hash_short
                        and link.nominal_revision != parent.latest_revision.hash_long
                    ):
                        link.is_suspicious = True

            if link.is_suspicious:
                actual_rev_obj = parent.latest_revision
                actual_rev_str = 'None'
                if actual_rev_obj:
                    actual_rev_str = f'{actual_rev_obj.hash_short} ({actual_rev_obj.timestamp.strftime("%Y-%m-%d %H:%M")} by {actual_rev_obj.author_email})'

                suspicious_links.append(
                    {
                        'artifact_aid': a.aid,
                        'artifact_atype': a.atype,
                        'parent_aid': parent.aid,
                        'parent_atype': parent.atype,
                        'nominal_revision': link.nominal_revision,
                        'actual_revision': actual_rev_str,
                    }
                )

    impact_data['suspicious_links'] = suspicious_links
    impact_data['total_suspicious'] = len(suspicious_links)

    if suspicious_links:
        suspicious_aids = {link['artifact_aid'] for link in suspicious_links}
        updated_aids = {link['parent_aid'] for link in suspicious_links}
        impact_data['suspicious_tree'] = _generate_suspicious_tree(artifacts, suspicious_aids, updated_aids)

    return impact_data


CONST_I_CHAR = '│'
CONST_T_CHAR = '├─'
CONST_L_CHAR = '└─'


def _generate_suspicious_tree(artifacts: ArtifactMap, suspicious_aids: set[str], updated_aids: set[str]) -> str:
    cache: dict[str, bool] = {}

    def has_suspicious_descendant(aid: str) -> bool:
        if aid in cache:
            return cache[aid]
        res = False
        if aid in suspicious_aids:
            res = True
        elif aid in artifacts:
            for cid in artifacts[aid].children:
                if has_suspicious_descendant(cid):
                    res = True
                    break
        cache[aid] = res
        return res

    def render_node(aid: str, indent: str = '', last: bool = True, top: bool = True) -> str:
        if not has_suspicious_descendant(aid):
            return ''

        if aid not in artifacts:
            return ''

        a = artifacts[aid]
        this_indent = indent + (CONST_L_CHAR if last else CONST_T_CHAR) if not top else ''

        status = ''
        if aid in suspicious_aids:
            status += ' [!] OUTDATED'
        if aid in updated_aids:
            status += ' [*] UPDATED'

        label = f'{a.atype}:{a.aid}' if a.atype != 'ROOT' else a.aid
        line = f'{this_indent}{label}{status}\n'

        new_indent = indent + ((CONST_I_CHAR + ' ') if not last else '  ') if not top else ''

        relevant_children = [cid for cid in sorted(a.children) if has_suspicious_descendant(cid)]

        res = line
        for i, cid in enumerate(relevant_children):
            res += render_node(cid, new_indent, i == len(relevant_children) - 1, False)

        return res

    return render_node('ROOT').strip()
