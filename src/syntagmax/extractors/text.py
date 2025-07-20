# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from text files (primarily, source code).

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
    lineno,
    alphanums
)

from syntagmax.config import Params
from syntagmax.artifact import ArtifactBuilder, Artifact, ValidationError
from syntagmax.extractors.extractor import Extractor, ExtractorResult

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

    def driver(self) -> str:
        return 'text'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        artifacts: Sequence[Artifact] = []
        errors : list[str] = []
        text = filepath.read_text(encoding='utf-8')
        matches = Begin.scanString(text)

        for match in matches:
            start_location = match[1]
            remaining_string = text[start_location:]
            section_start_string = remaining_string.split('\n', 1)[0]
            line = lineno(start_location, text)
            location = self._format_location(filepath, line)
            lg.debug(f'Found section, parsing: {section_start_string}')
            
            try:
                section: list[IdRef | PidRef] = Section.parse_string(remaining_string)  # type: ignore
                builder = ArtifactBuilder('text', location)

                for item in section:
                    if isinstance(item, IdRef):
                        builder.add_id(item.aid, item.atype)

                    if isinstance(item, PidRef):
                        builder.add_pid(item.aid, item.atype)

                artifact = builder.build()
                artifacts.append(artifact)

            except ParseException as e:
                error = self._format_error(
                    'Parse Error', location, line, section_start_string, str(e)
                )

                errors.append(error)

            except ValidationError as e:
                error = self._format_error(
                    'Malformed artifact', location, line, section_start_string, str(e)
                )

                errors.append(error)

        return artifacts, errors

    def _format_error(
        self, error_type: str, location: str, line: int, 
        section_start_string: str, message: str
    ) -> str:
        return f'''Driver "text": {error_type} in {location}@{line}
        While analyzing {section_start_string}
        Reason: {message}
        '''

    def _format_location(self, filepath: Path, line: int) -> str:
        return f'{self._format_file_location(filepath)}:{line}'
