"""Plugin: strip-marker

Demonstrates the transform_blocks hook.
Removes all [MARKER]...[/MARKER] tagged regions from TextBlock content
where MARKER matches the configured 'marker' param.
"""

import re

from syntagmax.blocks import BlockTree, TextBlock


def transform_blocks(tree: BlockTree, config, params: dict) -> BlockTree:
    marker = params.get('marker', '')
    if not marker:
        return tree

    pattern = re.compile(
        rf'\[{re.escape(marker)}\].*?\[/{re.escape(marker)}\]',
        re.DOTALL | re.IGNORECASE,
    )

    for input_block in tree.inputs:
        for file_record in input_block.files:
            for block in file_record.blocks:
                if isinstance(block, TextBlock) and block.marker is None:
                    block.content = pattern.sub('', block.content)

    return tree
