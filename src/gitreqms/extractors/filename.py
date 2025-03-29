import logging as lg

from git import Repo

from gitreqms.config import Params, InputRecord
from gitreqms.errors import InvalidArtifactIdentifier, InvalidArtifactType
from gitreqms.artifact import Artifact


class FilenameArtifact(Artifact):
    def __init__(self, atype: str, aid: str, description: str):
        super().__init__(atype, aid)
        self.description = description

    def driver(self) -> str:
        return 'filename'

    def metastring(self) -> str:
        return f'{self.description}'


class FilenameExtractor:
    def __init__(self, params: Params, repo: Repo, record: InputRecord):
        lg.debug(f'FilenameExtractor initialized {record["record_base"].name}')
        self._params = params
        self._repo = repo
        self._record = record

    def loglabel(self) -> str:
        return 'FILENAME'

    def extract(self) -> list[FilenameArtifact]:
        model = self._params['model']
        artifacts: list[FilenameArtifact] = []

        for filepath in self._record['filepaths']:
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

            artifacts.append(FilenameArtifact(atype, aid, description))

        return artifacts
