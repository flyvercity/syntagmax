# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06

from gitreqms.extractors.filename import FilenameExtractor

class ObsidianExtractor(FilenameExtractor):
    def driver(self) -> str:
        return 'obsidian'
