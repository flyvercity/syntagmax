# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from Obsidian files

from syntagmax.extractors.markdown import MarkdownExtractor

class ObsidianExtractor(MarkdownExtractor):
    def driver(self) -> str:
        return 'obsidian'
