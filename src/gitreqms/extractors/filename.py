import logging as lg

from git import Repo

from gitreqms.config import InputRecord


class FilenameExtractor:
    def __init__(self, repo: Repo, record: InputRecord):
        lg.debug(f'FilenameExtractor initialized {record["record_base"].name}')
        self._repo = repo
        self._record = record

    def extract(self):
        for filepath in self._record['filepaths']:
            lg.debug(f'Processing blob file: {filepath}')
