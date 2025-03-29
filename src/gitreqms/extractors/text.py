import logging as lg
from pathlib import Path
from typing import Sequence, TypedDict

from pyparsing import (
    Literal,
    Suppress,
    SkipTo,
    ParseException,
    ZeroOrMore,
    Regex,
    OneOrMore,
    Word,
    alphanums
)

from gitreqms.config import Params, InputRecord
from gitreqms.artifact import Artifact
from gitreqms.extractors.extractor import Extractor
from gitreqms.errors import RMSException


class TextParseError(RMSException):
    def __init__(self, message: str):
        super().__init__(f'Text Extractor Error: {message}')


class TextArtifact(Artifact):
    def __init__(self, atype: str, aid: str):
        super().__init__(atype, aid)

    def driver(self) -> str:
        return 'text'

    def metastring(self) -> str:
        return ''

class HeaderDef(TypedDict):
    aid: str
    atype: str
    pids: list[str]


Begin = Suppress(Literal('[<'))
BodyStart = Suppress(Literal('>>>'))
End = Suppress(Literal('>]'))
Equal = Suppress(Literal('='))
AID = Literal('ID') + Equal + Word(alphanums + '-')
PID = Literal('PID') + Equal + Word(alphanums + '-@')
Header = OneOrMore(AID | PID).set_parse_action(
    lambda t: HeaderDef(aid=t[0], atype='', pids=[]) # type: ignore
)

HeaderSkip = ZeroOrMore(~Begin + ~End + ~BodyStart + Suppress(Regex('.')))
BodySkip = ZeroOrMore(~Begin + ~End + ~BodyStart + Suppress(Regex('.')))
Section = Begin + Header + HeaderSkip + BodyStart + BodySkip + End

class TextExtractor(Extractor):
    def __init__(self, params: Params):
        self._params = params

    def extract_from_file(self, filepath: Path) -> Sequence[Artifact]:
        text = filepath.read_text()
        matches = Begin.scanString(text)

        for match in matches:
            start_location = match[1]
            remaining_string = text[start_location:]
            
            try:
                section = Section.parse_string(remaining_string)
            except ParseException as e:
                raise TextParseError(str(e))

            print(section)

        return []

    def extract(self, record: InputRecord) -> Sequence[Artifact]:
        artifacts: list[Artifact] = []

        for filepath in record['filepaths']:
            lg.debug(f'Processing text file: {filepath}')
            artifacts.extend(self.extract_from_file(filepath))

        return artifacts
