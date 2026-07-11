# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from Obsidian files

from pathlib import Path

from syntagmax.blocks import Block, TextBlock, ArtifactBlock
from syntagmax.extractors.markdown import MarkdownExtractor, apply_soft_line_breaks


class ObsidianExtractor(MarkdownExtractor):
    def driver(self) -> str:
        return 'obsidian'

    def extract_blocks_from_file(self, filepath: Path) -> list[Block]:
        blocks = super().extract_blocks_from_file(filepath)

        # Apply soft line break transformation when strict mode is OFF
        if not self._config.resolve_strict_line_breaks():
            for block in blocks:
                if isinstance(block, TextBlock):
                    block.content = apply_soft_line_breaks(block.content)
                elif isinstance(block, ArtifactBlock):
                    contents = block.artifact.fields.get('contents')
                    if contents and isinstance(contents, str):
                        block.artifact.fields['contents'] = apply_soft_line_breaks(contents)

        return blocks
