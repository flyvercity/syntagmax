# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from text files (primarily, source code).

import logging as lg
from pathlib import Path
from typing import Sequence

from pyparsing import (
    CaselessLiteral,
    Suppress,
    ParseException,
    ZeroOrMore,
    Regex,
    OneOrMore,
    Word,
    lineno,
    alphanums,
    alphas
)

from syntagmax.config import Config, InputRecord
from syntagmax.artifact import (
    ArtifactBuilder, Artifact, ValidationError, LineLocation
)
from syntagmax.extractors.extractor import Extractor, ExtractorResult


class Ref:
    atype: str
    aid: str

    def __init__(self, atype: str, aid: str):
        self.atype = atype
        self.aid = aid


class IdRef(Ref):
    def __init__(self, aid: str):
        self.value = aid


class ATypeRef(Ref):
    def __init__(self, atype: str):
        self.value = atype


class PidRef(Ref):
    revision: str

    def __init__(self, atype: str, aid: str, revision: str):
        super().__init__(atype, aid)
        self.revision = revision


Begin = Suppress(CaselessLiteral('[<'))
BodyStart = Suppress(CaselessLiteral('>>>'))
End = Suppress(CaselessLiteral('>]'))
Equal = Suppress(CaselessLiteral('='))
AType = Word(alphas, alphanums)
AId = Word(alphas, alphanums + '-')
Colon = Suppress(CaselessLiteral(':'))
At = Suppress(CaselessLiteral('@'))
IdKeyword = Suppress(CaselessLiteral('ID'))
ATypeKeyword = Suppress(CaselessLiteral('TYPE'))
PidKeyword = Suppress(CaselessLiteral('PID'))
Revision = Word(alphanums)

IdDirective = (IdKeyword + Equal + AId).set_parse_action(
    lambda t: IdRef(aid=t[0])  # type: ignore
)

ATypeDirective = (ATypeKeyword + Equal + AType).set_parse_action(
    lambda t: ATypeRef(atype=t[0])  # type: ignore
)

PidDirective = (PidKeyword + Equal + AType + Colon + AId + At + Revision).set_parse_action(
    lambda t: PidRef(atype=t[0], aid=t[1], revision=t[2])  # type: ignore
)

Header = OneOrMore(IdDirective | PidDirective).set_parse_action(
    lambda t: t
)

HeaderSkip = ZeroOrMore(~Begin + ~End + ~BodyStart + Suppress(Regex('.')))
BodySkip = ZeroOrMore(~Begin + ~End + ~BodyStart + Suppress(Regex('.')))

Section = (
    Begin + Header + HeaderSkip + BodyStart + BodySkip + End
).set_parse_action(
    lambda t: t
)


class TextArtifact(Artifact):
    def __init__(self, config: Config):
        super().__init__(config)


class TextExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord):
        super().__init__(config, record)

    def driver(self) -> str:
        return 'text'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        artifacts: Sequence[Artifact] = []
        errors: list[str] = []
        text = filepath.read_text(encoding='utf-8')
        matches = Begin.scanString(text)
        file_location = self._config.derive_path(filepath)

        for match in matches:
            start_location = match[1]
            end_location = match[2]

            remaining_string = text[start_location:]
            section_start_string = remaining_string.split('\n', 1)[0]
            start_line = lineno(start_location, text)

            lg.debug(f'Found section, parsing: {section_start_string}')

            location = LineLocation(
                loc_file=file_location,
                loc_lines=(start_line, end_location)
            )

            try:
                section = Section.parse_string(remaining_string)

                builder = ArtifactBuilder(
                    self._config,
                    TextArtifact,
                    'text',
                    location
                )

                aid: str | None = None
                atype: str | None = self._record['default_atype']

                for item in section:  # type: ignore
                    if isinstance(item, IdRef):
                        aid = item.value
                    if isinstance(item, ATypeRef):
                        atype = item.value
                    elif isinstance(item, PidRef):
                        builder.add_pid(item.aid, item.atype)

                if aid is None:
                    error = self._format_error(
                        'Missing ID', location, section_start_string, 'ID is required'
                    )
                    errors.append(error)
                    continue

                builder.add_id(aid, atype)
                artifact = builder.build()
                artifacts.append(artifact)

            except ParseException as e:
                error = self._format_error(
                    'Parse Error', location, section_start_string, str(e)
                )

                errors.append(error)

            except ValidationError as e:
                error = self._format_error(
                    'Malformed artifact',
                    location,
                    section_start_string, str(e)
                )

                errors.append(error)

        return artifacts, errors

    def _format_error(
        self, error_type: str, location: LineLocation,
        section_start_string: str, message: str
    ) -> str:
        return f'''Driver "text": {error_type} in {location}
        While analyzing {section_start_string}
        Reason: {message}
        '''
