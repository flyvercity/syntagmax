import logging as lg

from git import Repo

from gitreqms.config import Params, InputRecord
from gitreqms.artifact import Artifact

class TextExtractor:
    def __init__(self, params: Params, repo: Repo, record: InputRecord):
        lg.debug(f'TextExtractor initialized {record["record_base"].name}')
        self._params = params
        self._repo = repo
        self._record = record

    def extract(self) -> list[Artifact]:
        for filepath in self._record['filepaths']:
            lg.debug(f'Processing text file: {filepath}')

        return []
