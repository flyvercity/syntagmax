import logging as lg
from pathlib import Path
from typing import Sequence

from gitreqms.config import Params, InputRecord
from gitreqms.errors import InvalidArtifactIdentifier, InvalidArtifactType
from gitreqms.artifact import Artifact
from gitreqms.extractors.extractor import Extractor

class FilenameArtifact(Artifact):
    def __init__(self, atype: str, aid: str, description: str):
        super().__init__(atype, aid)
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

    def extract_from_file(self, filepath: Path) -> Sequence[FilenameArtifact]:
        model = self._params['model']
        lg.debug(f'Processing blob file: {filepath}')

        filename = filepath.stem
        filename_split = filename.split(' ', 1)

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

        if not model.isValidAType(atype):
            raise InvalidArtifactType(
                f'{self.loglabel()} :: Invalid artifact type: {atype}'
            )

        return [FilenameArtifact(atype, aid, description)]
        

    def extract(self, record: InputRecord) -> Sequence[Artifact]:
        artifacts: list[Artifact] = []

        for filepath in record['filepaths']:
            artifacts.extend(self.extract_from_file(filepath))

        return artifacts
