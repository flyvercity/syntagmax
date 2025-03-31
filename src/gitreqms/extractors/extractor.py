from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence
import logging as lg

from gitreqms.config import InputRecord
from gitreqms.artifact import Artifact


class Extractor(ABC):
    @abstractmethod
    def extract_from_file(self, filepath: Path) -> tuple[Sequence[Artifact], list[str]]:
        pass

    def extract(self, record: InputRecord) -> tuple[Sequence[Artifact], list[str]]:
        errors : list[str] = []
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