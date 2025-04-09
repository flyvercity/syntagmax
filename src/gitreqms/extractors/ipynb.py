
# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-09
# Description: Extracts artifacts from ipynb files.

from pathlib import Path
import json
import traceback
import logging as lg

from gitreqms.config import Params
from gitreqms.extractors.markdown import MarkdownExtractor
from gitreqms.extractors.extractor import ExtractorResult
from gitreqms.artifact import Artifact

class IPynbExtractor(MarkdownExtractor):
    def __init__(self, params: Params):
        super().__init__(params)

    def driver(self) -> str:
        return 'ipynb'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        try:
            notebook = json.loads(filepath.read_text())
            location = self._format_file_location(filepath)
            artifacts: list[Artifact] = []
            errors: list[str] = []

            for cell in notebook['cells']:
                if cell['cell_type'] == 'markdown':
                    markdown = ''.join(cell['source'])
                    cell_artifacts, cell_errors = self._extract_from_markdown(location, markdown)
                        
                    # NB: allowing only one artifact per file
                    if not artifacts:
                        artifacts.extend(cell_artifacts)
                    else:
                        error = f'Multiple artifacts found in {location}'
                        errors.append(error)

                    errors.extend(cell_errors)

            return artifacts, errors

        except Exception as e:
            if self._params['verbose']:
                lg.error(f'Error extracting from {filepath}: {e}, {traceback.format_exc()}')

            message = f'Error extracting from {filepath}: {e}'
            return [], [message]
