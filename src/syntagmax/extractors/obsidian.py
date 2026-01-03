# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from Obsidian files
from pathlib import Path
import pyparsing as pp

from syntagmax.extractors.extractor import Extractor, ExtractorResult
from syntagmax.config import Config, InputRecord


class ObsidianExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord):
        super().__init__(config, record)

    def driver(self) -> str:
        return 'obsidian'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        markdown = filepath.read_text(encoding='utf-8')
        record_base = self._record['record_base']
        location = f'file://{filepath.relative_to(record_base)}'
        return self._extract_from_markdown(location, markdown)

    def _extract_from_markdown(self, location: str, markdown: str) -> ExtractorResult:
        return [], []


def create_grammar():
    pass
    
