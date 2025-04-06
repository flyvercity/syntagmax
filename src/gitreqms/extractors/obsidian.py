# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06

from gitreqms.extractors.filename import FilenameArtifact, FilenameExtractor

class ObsidianArtifact(FilenameArtifact):
    def driver(self) -> str:
        return 'obsidian'

class ObsidianExtractor(FilenameExtractor):
    def loglabel(self) -> str:
        return 'OBSIDIAN'

    def create_artifact(self, location: str, atype: str, aid: str, description: str) -> FilenameArtifact:
        return ObsidianArtifact(location, atype, aid, description)
