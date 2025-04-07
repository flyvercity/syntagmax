# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-07
# Description: Prints a tree of artifacts.

from gitreqms.artifact import Artifact, ArtifactMap, ARef
import gitreqms.utils as u

CONST_I_CHAR = '│'
CONST_T_CHAR = '├─'
CONST_L_CHAR = '└─'

def print_artifact(artifact: Artifact, indent: str, last: bool, top: bool):
    this_indent = indent + (CONST_L_CHAR if last else CONST_T_CHAR) if not top else ' '
    u.pprint(f'{this_indent}[cyan]{artifact.atype}[/cyan]: [green]{artifact.aid}[/green]')
    metastring = artifact.metastring()
    has_children = bool(artifact.children)

    detail_indent = (
        indent + (CONST_I_CHAR if not last else ' ') 
        + ' '
        + (CONST_I_CHAR if has_children else ' ')
        + (' ' *  2)
    )
        
    if metastring:
        u.pprint(f'{detail_indent}{metastring}')

def print_arttree(artifacts: ArtifactMap, ref: ARef, indent: str ="", last: bool = True, top: bool = True):
    artifact = artifacts[ref]
    print_artifact(artifact, indent, last, top)
    children = list(sorted(artifact.children, key=lambda c: c.aid))
    indent += (CONST_I_CHAR if not last else ' ') + ' '

    for child in children[:-1]:
        print_arttree(artifacts, child, indent, False, False)

    if children:
        print_arttree(artifacts, children[-1], indent, True, False)
    