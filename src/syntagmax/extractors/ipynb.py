# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-09
# Description: Extracts artifacts from ipynb files.

from pathlib import Path
import json

from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.extractors.extractor import ExtractorResult
from syntagmax.artifact import NotebookLocation


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
