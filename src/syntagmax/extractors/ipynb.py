# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-09
# Description: Extracts artifacts from ipynb files.

from pathlib import Path
import json
import re

from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.extractors.extractor import ExtractorResult
from syntagmax.artifact import NotebookLocation
from syntagmax.blocks import Block, TextBlock, ArtifactBlock


class IPynbExtractor(MarkdownExtractor):
    def driver(self) -> str:
        return 'ipynb'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        try:
            notebook = json.loads(filepath.read_text(encoding='utf-8'))
            loc_file = self._config.derive_path(filepath)
            artifacts = []
            errors = []

            for i, cell in enumerate(notebook['cells']):
                if cell['cell_type'] == 'markdown':
                    markdown = ''.join(cell['source'])

                    def location_builder(start, end, idx=i):
                        return NotebookLocation(loc_file=loc_file, loc_lines=(start, end), loc_cell=idx)

                    cell_artifacts, cell_errors = self._extract_from_markdown(filepath, markdown, location_builder)
                    errors.extend(cell_errors)
                    artifacts.extend(cell_artifacts)

            return artifacts, errors

        except Exception as e:
            message = f'Error extracting from {filepath}: {e}'
            return [], [message]

    def extract_blocks_from_file(self, filepath: Path) -> list[Block]:
        try:
            notebook = json.loads(filepath.read_text(encoding='utf-8'))
        except Exception:
            return []

        blocks: list[Block] = []
        marker = self._record.marker
        marker_pattern = re.compile(rf'\[{marker}\]', re.IGNORECASE)

        for cell in notebook.get('cells', []):
            source = ''.join(cell.get('source', []))
            if cell.get('cell_type') == 'markdown' and marker_pattern.search(source):
                blocks.extend(self._extract_blocks_from_markdown(source))
            else:
                blocks.append(TextBlock(content=source))

        return blocks

    def _extract_blocks_from_markdown(self, markdown: str) -> list[Block]:
        marker = self._record.marker
        marker_pattern = re.compile(rf'\[{marker}\]', re.IGNORECASE)
        blocks: list[Block] = []
        pos = 0

        while pos < len(markdown):
            match = marker_pattern.search(markdown, pos)
            if not match:
                remaining = markdown[pos:]
                if remaining.strip():
                    blocks.append(TextBlock(content=remaining))
                break

            # Text before the artifact
            if match.start() > pos:
                before = markdown[pos:match.start()]
                if before.strip():
                    blocks.append(TextBlock(content=before))

            # Find terminator
            start_pos = match.start()
            yaml_start = markdown.find('```yaml', start_pos)
            slash_match = re.search(rf'\[/{marker}\]', markdown[start_pos:], re.IGNORECASE)
            slash_pos = (start_pos + slash_match.start()) if slash_match else -1

            segment_end = -1
            if yaml_start != -1 and (slash_pos == -1 or yaml_start < slash_pos):
                end_pos = markdown.find('```', yaml_start + 7)
                if end_pos != -1:
                    segment_end = end_pos + 3
            elif slash_pos != -1:
                segment_end = slash_pos + len(f'[/{marker}]')

            if segment_end == -1:
                blocks.append(TextBlock(content=markdown[start_pos:]))
                break

            raw_text = markdown[start_pos:segment_end]

            # Try to parse the artifact
            start_line = markdown.count('\n', 0, start_pos) + 1
            end_line = markdown.count('\n', 0, segment_end) + 1

            from syntagmax.artifact import LineLocation

            def location_builder(s, e):
                return LineLocation(loc_file='', loc_lines=(s, e))

            artifacts, _ = self._extract_from_markdown(Path(''), raw_text, location_builder)
            if artifacts:
                blocks.append(ArtifactBlock(artifact=artifacts[0], raw_text=raw_text))
            else:
                blocks.append(TextBlock(content=raw_text))

            pos = segment_end

        return blocks
