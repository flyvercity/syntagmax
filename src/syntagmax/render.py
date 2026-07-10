# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Prints a tree of artifacts and other console output.

from syntagmax.artifact import Artifact, ArtifactMap

CONST_I_CHAR = '│'
CONST_T_CHAR = '├─'
CONST_L_CHAR = '└─'


def render_tree_markdown(artifacts: ArtifactMap, ref: str = 'ROOT', verbose: bool = False) -> str:
    lines: list[str] = []

    def _render_artifact(artifact: Artifact, indent: str, last: bool, top: bool, has_children: bool):
        this_indent = indent + (CONST_L_CHAR if last else CONST_T_CHAR) if not top else ' '
        lines.append(f'{this_indent}{artifact.atype}: {artifact.aid}')

        if top:
            return

        branch_line = CONST_I_CHAR if not last else ' '
        children_line = CONST_I_CHAR if has_children else ' '
        detail_indent = indent + branch_line + ' ' + children_line

        lines.append(f'{detail_indent} {artifact}')

        pids_str_list = []
        if artifact.parent_links:
            for link in artifact.parent_links:
                s = link.pid
                if link.nominal_revision:
                    s += f'@{link.nominal_revision}'
                if link.is_suspicious:
                    s += ' [!]'
                pids_str_list.append(s)
        else:
            pids_str_list = [str(pid) for pid in artifact.pids]

        pids_str = ', '.join(pids_str_list)
        lines.append(f'{detail_indent} Parents: [{pids_str}]')

        if artifact.revisions:
            lines.append(f'{detail_indent} Revisions:')
            rev_list = sorted(list(artifact.revisions), key=lambda r: r.timestamp, reverse=True)
            for r in rev_list:
                rev_str = f'{r.hash_short} ({r.timestamp.strftime("%Y-%m-%d %H:%M")} by {r.author_email})'
                lines.append(f'{detail_indent}  - {rev_str}')

        lines.append(f'{detail_indent} Attributes:')
        for field in artifact.fields:
            field_str = str(artifact.fields[field])
            if len(field_str) > 60:
                field_str = field_str.split()[0]
                field_str = field_str[0:60] + '...'
            lines.append(f'{detail_indent}  - {field}: {field_str}')

    def _render_tree(ref: str, indent: str = '', last: bool = True, top: bool = True):
        artifact = artifacts[ref]
        children = sorted(artifact.children, key=lambda c: artifacts[c].aid)
        _render_artifact(artifact, indent, last, top, bool(children))
        indent += (CONST_I_CHAR if not last else ' ') + ' '

        for child_id in children[:-1]:
            _render_tree(child_id, indent, False, False)

        if children:
            _render_tree(children[-1], indent, True, False)

    _render_tree(ref)
    return '\n'.join(lines)
