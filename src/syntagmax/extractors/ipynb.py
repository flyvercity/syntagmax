# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-09
# Description: Extracts artifacts from ipynb files.

from pathlib import Path
import json
import re

from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.artifact import NotebookLocation
from syntagmax.blocks import Block, TextBlock, ErrorBlock


class IPynbExtractor(MarkdownExtractor):
    def driver(self):
        return 'ipynb'

    def extract_blocks_from_file(self, filepath: Path) -> list[Block]:
        try:
            notebook = json.loads(filepath.read_text(encoding='utf-8'))
        except Exception as e:
            return [ErrorBlock(message=f'Error extracting from {filepath}: {e}', raw_text='')]

        loc_file = self._config.derive_path(filepath)
        blocks: list[Block] = []
        marker = self._record.marker
        marker_pattern = re.compile(rf'\[{marker}\]', re.IGNORECASE)

        for cell_idx, cell in enumerate(notebook.get('cells', [])):
            source = ''.join(cell.get('source', []))

            if cell.get('cell_type') == 'markdown' and marker_pattern.search(source):

                def location_builder(start, end, ci=cell_idx):
                    return NotebookLocation(loc_file=loc_file, loc_lines=(start, end), loc_cell=ci)

                cell_blocks = self._extract_blocks_from_markdown(filepath, source, location_builder)
                blocks.extend(cell_blocks)
            else:
                if source:
                    blocks.append(TextBlock(content=source))

        return blocks
