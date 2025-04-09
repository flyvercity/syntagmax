# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29

import logging as lg
from pathlib import Path
from typing import Sequence

from gitreqms.config import Params
from gitreqms.artifact import ArtifactBuilder, Artifact
from gitreqms.extractors.extractor import Extractor


class FilenameExtractor(Extractor):
    def __init__(self, params: Params):
        self._params = params

    def driver(self) -> str:
        return 'filename'

    def extract_from_file(self, filepath: Path) -> tuple[Sequence[Artifact], list[str]]:
        lg.debug(f'Processing blob file: {filepath}')
        filename = filepath.stem
        filename_split = filename.split(' ')

        if len(filename_split) < 1:
            return [], [f'{self.driver()} :: Invalid identifier: {filename}']

        handle = filename_split[0].strip()
        description = filename_split[1].strip() if len(filename_split) > 1 else ''
        handle_split = handle.split('-')

        if len(handle_split) < 2:
            return [], [f'{self.driver()} :: Invalid identifier: {filename}']

        atype = handle_split[0]
        aid = '-'.join(handle_split[1:])
        location = self._format_file_location(filepath)
        builder = ArtifactBuilder(self.driver(), location)
        builder.add_id(aid, atype)
        builder.add_desc(description)
        return [builder.build()], []
