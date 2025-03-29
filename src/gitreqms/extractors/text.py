import logging as lg
from pathlib import Path
from typing import Sequence

from pyparsing import (
    Literal,
    Suppress,
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

class Ref:
    atype: str
    aid: str

    def __init__(self, atype: str, aid: str):
        self.atype = atype
        self.aid = aid

class IdRef(Ref):
    pass

class PidRef(Ref):
    revision: str

    def __init__(self, atype: str, aid: str, revision: str):
        super().__init__(atype, aid)
        self.revision = revision


Begin = Suppress(Literal('[<'))
BodyStart = Suppress(Literal('>>>'))
End = Suppress(Literal('>]'))
Equal = Suppress(Literal('='))
AType = Word(alphanums)
AId = Word(alphanums + '-')
Hyphen = Suppress(Literal('-'))
At = Suppress(Literal('@'))
IdKeyword = Suppress(Literal('ID'))
PidKeyword = Suppress(Literal('PID'))
Revision = Word(alphanums)

IdDirective = (IdKeyword + Equal + AType + Hyphen + AId).set_parse_action(
    lambda t: IdRef(atype=t[0], aid=t[1])  # type: ignore
)

PidDirective = (PidKeyword + Equal + AType + Hyphen + AId + At + Revision).set_parse_action(
    lambda t: PidRef(atype=t[0], aid=t[1], revision=t[2])  # type: ignore
)

Header = OneOrMore(IdDirective | PidDirective).set_parse_action(
    lambda t: t
)

HeaderSkip = ZeroOrMore(~Begin + ~End + ~BodyStart + Suppress(Regex('.')))
BodySkip = ZeroOrMore(~Begin + ~End + ~BodyStart + Suppress(Regex('.')))

Section = (Begin + Header + HeaderSkip + BodyStart + BodySkip + End).set_parse_action(
    lambda t: t
)

class TextExtractor(Extractor):
    def __init__(self, params: Params):
        self._params = params

    def extract_from_file(self, filepath: Path) -> Sequence[Artifact]:
        text = filepath.read_text()
        matches = Begin.scanString(text)

        for match in matches:
            start_location = match[1]
            remaining_string = text[start_location:]
            section_start_string = remaining_string.split('\n', 1)[0]
            lg.debug(f'Found section, parsing: {section_start_string}')
            
            try:
                section = Section.parse_string(remaining_string)
            except ParseException as e:
                raise TextParseError(f'{str(e)}: at {section_start_string}')

            print(section)

        return []

    def extract(self, record: InputRecord) -> Sequence[Artifact]:
        artifacts: list[Artifact] = []

        for filepath in record['filepaths']:
            lg.debug(f'Processing text file: {filepath}')
            artifacts.extend(self.extract_from_file(filepath))

        return artifacts
