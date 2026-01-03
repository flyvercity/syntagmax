# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from text files (primarily, source code).

import logging as lg
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

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

from syntagmax.config import Config, InputRecord
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


def capture_begin_position(s, loc, tokens):
    return {'type': 'begin', 'line': lineno(loc, s)}


def capture_end_position(s, loc, tokens):
    return {'type': 'end', 'line': lineno(loc, s)}


Begin = Literal('[<').set_parse_action(capture_begin_position)
BodyStart = Suppress(Literal('>>>'))
End = Literal('>]').set_parse_action(capture_end_position)
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

Section = (
    Begin + Header + HeaderSkip + BodyStart + BodySkip + End
).set_parse_action(
    lambda t: t
)


class TextArtifact(Artifact):
    def contents(self) -> str:
        uri = urlparse(self.location)
        assert uri.scheme == 'line'
        filepath_str = f'{uri.netloc}/{uri.path}'
        line = uri.fragment
        filepath = self._config.base_dir() / filepath_str
        text = filepath.read_text(encoding='utf-8')
        begin, end = line.split('-')
        return text.split('\n')[int(begin) - 1:int(end) - 2]


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

        for match in matches:
            start_location = match[1]
            remaining_string = text[start_location:]
            section_start_string = remaining_string.split('\n', 1)[0]
            start_line = lineno(start_location, text)
            file_location = self._config.derive_path(filepath)
            location = f'line://{file_location}#{start_line}'

            lg.debug(f'Found section, parsing: {section_start_string}')

            try:
                section = Section.parse_string(remaining_string)

                # Extract line numbers from Begin and End tokens
                begin = start_line
                end = start_line

                for item in section:
                    if isinstance(item, dict):
                        if item.get('type') == 'begin':
                            begin += item.get('line')
                        elif item.get('type') == 'end':
                            end += item.get('line')

                # Refine position
                location = f'line://{file_location}#{begin}-{end}'

                builder = ArtifactBuilder(
                    self._config,
                    TextArtifact,
                    'text',
                    location
                )

                for item in section:
                    if isinstance(item, IdRef):
                        builder.add_id(item.aid, item.atype)
                    elif isinstance(item, PidRef):
                        builder.add_pid(item.aid, item.atype)
                    # Skip Begin and End token dictionaries - they're just for line number tracking

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
        self, error_type: str, location: str,
        section_start_string: str, message: str
    ) -> str:
        return f'''Driver "text": {error_type} in {location}
        While analyzing {section_start_string}
        Reason: {message}
        '''
