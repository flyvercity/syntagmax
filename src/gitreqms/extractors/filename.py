# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29

import logging as lg
from pathlib import Path
from typing import Sequence

from gitreqms.config import Params
from gitreqms.errors import InvalidArtifactIdentifier
from gitreqms.artifact import Artifact
from gitreqms.extractors.extractor import Extractor

class FilenameArtifact(Artifact):
    def __init__(self, location: str, atype: str, aid: str, description: str):
        super().__init__(location, atype, aid)
        self.description = description

    def driver(self) -> str:
        return 'filename'

    def metastring(self) -> str:
        return f'{self.description}'


class FilenameExtractor(Extractor):
    def __init__(self, params: Params):
        self._params = params

    def loglabel(self) -> str:
        return 'FILENAME'

    def create_artifact(self, location: str, atype: str, aid: str, description: str) -> FilenameArtifact:
        return FilenameArtifact(location, atype, aid, description)
    
    def extract_from_file(self, filepath: Path) -> tuple[Sequence[FilenameArtifact], list[str]]:
        lg.debug(f'Processing blob file: {filepath}')

        filename = filepath.stem
        filename_split = filename.split(' ')

        if len(filename_split) < 1:
            raise InvalidArtifactIdentifier(
                f'{self.loglabel()} :: Invalid identifier: {filename}'
            )

        handle = filename_split[0].strip()
        description = filename_split[1].strip() if len(filename_split) > 1 else ''

        handle_split = handle.split('-')

        if len(handle_split) < 2:
            raise InvalidArtifactIdentifier(
                f'{self.loglabel()} :: Invalid identifier: {filename}'
            )

        atype = handle_split[0]
        aid = '-'.join(handle_split[1:])

        location = self._format_file_location(filepath)
        return [self.create_artifact(location, atype, aid, description)], []
