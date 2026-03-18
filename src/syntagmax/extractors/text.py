# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from text files (primarily, source code).

import logging as lg
from pathlib import Path
from typing import Sequence

from lark import Lark, Transformer, exceptions

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


class TextTransformer(Transformer):
    def AID(self, t):
        return str(t)

    def ATYPE(self, t):
        return str(t)

    def REVISION(self, t):
        return str(t)

    def id_directive(self, t):
        return IdRef(aid=t[0])

    def type_directive(self, t):
        return ATypeRef(atype=t[0])

    def pid_directive(self, t):
        return PidRef(atype=t[0], aid=t[1], revision=t[2])

    def directive(self, t):
        return t[0]

    def header(self, t):
        return [item for item in t if isinstance(item, Ref)]

    def section(self, t):
        return t[0]


class TextArtifact(Artifact):
    def __init__(self, config: Config):
        super().__init__(config)


class TextExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord):
        super().__init__(config, record)
        grammar_path = Path(__file__).parent / 'text.lark'
        self._parser = Lark.open(
            grammar_path,
            rel_to=__file__,
            parser='lalr',
            maybe_placeholders=False
        )
        self._transformer = TextTransformer()

    def driver(self) -> str:
        return 'text'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        artifacts: Sequence[Artifact] = []
        errors: list[str] = []
        text = filepath.read_text(encoding='utf-8')
        file_location = self._config.derive_path(filepath)

        # Use a simple search for the start marker
        start_marker = '[<'
        pos = 0

        while True:
            start_pos = text.find(start_marker, pos)

            if start_pos == -1:
                break

            # Find the end marker to extract the segment
            end_marker = '>]'
            end_pos = text.find(end_marker, start_pos)

            if end_pos == -1:
                # Malformed segment, but we might want to report it
                break

            segment_end = end_pos + len(end_marker)
            segment = text[start_pos:segment_end]
            start_line = text.count('\n', 0, start_pos) + 1
            section_start_string = segment.split('\n', 1)[0]

            lg.debug(f'Found section at line {start_line}, parsing: {section_start_string}')

            location = LineLocation(
                loc_file=file_location,
                loc_lines=(start_line, segment_end)
            )

            try:
                tree = self._parser.parse(segment)
                section = self._transformer.transform(tree)

                builder = ArtifactBuilder(
                    self._config,
                    TextArtifact,
                    'text',
                    location
                )

                aid: str | None = None
                atype: str | None = self._record.default_atype

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
                    pos = segment_end
                    continue

                builder.add_id(aid, atype)
                artifact = builder.build()
                artifacts.append(artifact)

            except (exceptions.ParseError, exceptions.UnexpectedToken) as e:
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

            pos = segment_end

        return artifacts, errors

    def _format_error(
        self, error_type: str, location: LineLocation,
        section_start_string: str, message: str
    ) -> str:
        return f'''Driver "text": {error_type} in {location}
        While analyzing {section_start_string}
        Reason: {message}
        '''
