# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Prints a tree of artifacts and other console output.

import rich
from rich.table import Table
from benedict import benedict
from rich.markup import escape

from syntagmax.artifact import Artifact, ArtifactMap
import syntagmax.utils as u

CONST_I_CHAR = '│'
CONST_T_CHAR = '├─'
CONST_L_CHAR = '└─'
CONST_II_CHAR = '║'


def print_artifact(artifact: Artifact, indent: str, last: bool, top: bool, has_children: bool, verbose: bool = False):
    this_indent = indent + (CONST_L_CHAR if last else CONST_T_CHAR) if not top else ' '
    u.pprint(f'{this_indent}[cyan]{artifact.atype}[/cyan]: [green]{artifact.aid}[/green]')
    metastring = str(artifact)

    if top:
        return

    if has_children:
        detail_indent = indent + CONST_I_CHAR + ' ' + CONST_I_CHAR
    elif not last:
        detail_indent = indent + CONST_I_CHAR
    else:
        detail_indent = indent + '   '

    u.pprint(f'{detail_indent} [i]{metastring}[/i]')

    pids_str_list = []
    if artifact.parent_links:
        for link in artifact.parent_links:
            s = link.pid
            if link.nominal_revision:
                s += f'@{link.nominal_revision}'
            if link.is_suspicious:
                s = f'[yellow]{s}[/yellow]'
            pids_str_list.append(s)
    else:
        pids_str_list = [str(pid) for pid in artifact.pids]

    pids_str = ', '.join(pids_str_list)
    u.pprint(f'{detail_indent} Parents: [{pids_str}]')

    if artifact.revisions:
        u.pprint(escape(f'{detail_indent} Revisions:'))
        rev_list = sorted(list(artifact.revisions), key=lambda r: r.timestamp, reverse=True)

        for r in rev_list:
            rev_str = f'{r.hash_short} ({r.timestamp.strftime("%Y-%m-%d %H:%M")} by {r.author_email})'
            u.pprint(escape(f'{detail_indent}  - {rev_str}'))

    u.pprint(escape(f'{detail_indent} Attributes:'))
    for field in artifact.fields:
        field_str = str(artifact.fields[field])
        if len(field_str) > 60:
            field_str = field_str.split()[0]
            field_str = field_str[0:60] + '...'
        u.pprint(f'{detail_indent}  - {field}: {field_str}')


def print_arttree(
    artifacts: ArtifactMap, ref: str, indent: str = '', last: bool = True, top: bool = True, verbose: bool = False
):
    artifact = artifacts[ref]
    children = list(sorted(artifact.children, key=lambda c: artifacts[c].aid))
    print_artifact(artifact, indent, last, top, bool(children), verbose)
    indent += (CONST_I_CHAR if not last else ' ') + ' '

    for child_id in children[:-1]:
        print_arttree(artifacts, child_id, indent, False, False, verbose)

    if children:
        print_arttree(artifacts, children[-1], indent, True, False, verbose)


def print_metrics(metrics: benedict):
    table = Table(title='Artifact Metrics')
    table.add_column('Metric', style='cyan', no_wrap=True)
    table.add_column('Value', style='magenta')

    for k, v in metrics.items():
        table.add_row(str(k), str(v))

    rich.print(table)
