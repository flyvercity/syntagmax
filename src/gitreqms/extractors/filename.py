import logging as lg

from git import Repo

from gitreqms.config import Params, InputRecord
from gitreqms.errors import InvalidArtifactIdentifier, InvalidArtifactType
from gitreqms.artifact import Artifact


class BlobArtifact(Artifact):
    def __init__(self, atype: str, aid: str):
        super().__init__(atype, aid)


class FilenameExtractor:
    def __init__(self, params: Params, repo: Repo, record: InputRecord):
        lg.debug(f'FilenameExtractor initialized {record["record_base"].name}')
        self._params = params
        self._repo = repo
        self._record = record

    def extract(self) -> list[BlobArtifact]:
        model = self._params['model']
        artifacts: list[BlobArtifact] = []

        for filepath in self._record['filepaths']:
            lg.debug(f'Processing blob file: {filepath}')
            filename = filepath.stem

            split = filename.split('-')

            if len(split) < 2:
                raise InvalidArtifactIdentifier(f'FILENAME :: Invalid identifier: {filename}')
            
            atype = split[0]
            aid = '-'.join(split[1:])

            if not model.isValidAType(atype):
                raise InvalidArtifactType(f'FILENAME :: Invalid artifact type: {atype}')

            artifacts.append(BlobArtifact(atype, aid))

        return artifacts
            
