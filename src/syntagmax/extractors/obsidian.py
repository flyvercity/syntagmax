# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from Obsidian files

from pathlib import Path

from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.extractors.extractor import ExtractorResult
from syntagmax.artifact import LineLocation


class ObsidianExtractor(MarkdownExtractor):
    def driver(self) -> str:
        return 'obsidian'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        markdown = filepath.read_text(encoding='utf-8')
        loc_file = self._config.derive_path(filepath)

        def location_builder(start, end):
            return LineLocation(loc_file=loc_file, loc_lines=(start, end))

        return self._extract_from_markdown(filepath, markdown, location_builder)
