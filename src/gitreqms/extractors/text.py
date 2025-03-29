import logging as lg
from pathlib import Path

from git import Repo
from pyparsing import (
    Literal,
    Suppress,
    Any
)

from gitreqms.config import Params, InputRecord
from gitreqms.artifact import Artifact


class TextArtifact(Artifact):
    def __init__(self, text: str):
        self.text = text

    def driver(self) -> str:
        return 'text'


Begin = Suppress(Literal("[<]"))
Header = Any
BodyStart = Suppress(Literal('>>>'))
Body = Any
End = Suppress(Literal("[>]"))

# Section = Begin + Header + BodyStart + Body + End

class TextExtractor:
    def __init__(self, params: Params, repo: Repo, record: InputRecord):
        lg.debug(f'TextExtractor initialized {record["record_base"].name}')
        self._params = params
        self._repo = repo
        self._record = record

    def extract(self) -> list[Artifact]:
        artifacts = []

        for filepath in self._record['filepaths']:
            lg.debug(f'Processing text file: {filepath}')
            text = Path(filepath).read_text()

        return artifacts
