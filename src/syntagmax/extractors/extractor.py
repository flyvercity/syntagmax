# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Base class for all extractors.

from pathlib import Path
from typing import Sequence
import logging as lg

from syntagmax.config import InputRecord
from syntagmax.artifact import Artifact

type ExtractorResult = tuple[Sequence[Artifact], list[str]]


class Extractor:
    def driver(self) -> str: ...
    def extract_from_file(self, filepath: Path) -> ExtractorResult: ...

    def extract(self, record: InputRecord) -> tuple[Sequence[Artifact], list[str]]:
        errors: list[str] = []
        artifacts: list[Artifact] = []

        for filepath in record['filepaths']:
            lg.debug(f'Processing file: {filepath}')
            file_artifacts, file_errors = self.extract_from_file(filepath)
            artifacts.extend(file_artifacts)
            errors.extend(file_errors)

            if errors:
                lg.debug(f'Errors were reported for {filepath}')
            else:
                lg.debug(f'Successfully processed file: {filepath}')

        return artifacts, errors

    def _format_file_location(self, filepath: Path) -> str:
        names: list[str] = ['...']
        parents = filepath.parents

        if len(parents) >= 2:
            names.append(parents[1].name)

        if len(parents) >= 1:
            names.append(parents[0].name)

        names.append(filepath.name)

        return '/'.join(names)

    def _split_handle(self, handle: str) -> list[str]:
        return handle.split('-', 1)
