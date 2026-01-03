# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Extracts artifacts from filename only.

import logging as lg
from pathlib import Path

from syntagmax.config import Config
from syntagmax.artifact import ArtifactBuilder, Artifact
from syntagmax.extractors.extractor import Extractor, ExtractorResult


class FilenameExtractor(Extractor):
    def __init__(self, config: Config):
        self._config = config

    def driver(self) -> str:
        return 'filename'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        lg.debug(f'Processing blob file: {filepath}')
        filename = filepath.stem
        filename_split = filename.split(' ')

        if len(filename_split) < 1:
            return [], [f'{self.driver()} :: Invalid identifier: {filename}']

        handle = filename_split[0].strip()
        description = filename_split[1].strip() if len(filename_split) > 1 else ''
        handle_split = self._split_handle(handle)

        if len(handle_split) < 2:
            return [], [f'{self.driver()} :: Invalid identifier: {filename}']

        atype = handle_split[0]
        aid = handle_split[1]
        location = f'file://{self._config.derive_path(filepath)}'

        builder = ArtifactBuilder(
            self._config, Artifact, self.driver(), location
        )

        builder.add_id(aid, atype)
        builder.add_desc(description)
        return [builder.build()], []
