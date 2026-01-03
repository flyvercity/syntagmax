# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from Obsidian files
from pathlib import Path
import logging as lg

from pyparsing.helpers import Any
import rich
import pyparsing as pp

from syntagmax.extractors.extractor import Extractor, ExtractorResult
from syntagmax.config import Config, InputRecord


class ObsidianExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord):
        super().__init__(config, record)

    def driver(self) -> str:
        return 'obsidian'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        markdown = filepath.read_text(encoding='utf-8')
        record_base = self._record['record_base']
        location = f'file://{filepath.relative_to(record_base)}'
        return self._extract_from_markdown(location, markdown)

    def _extract_from_markdown(self, loc_file: str, markdown: str) -> ExtractorResult:
        req_grammar = create_grammar()
        req_match = req_grammar.scan_string(markdown)

        for (match, start, end) in req_match:
            if len(match) != 1:
                raise ValueError(f'Expected 1 match, got {len(match)}')

            req: dict = match[0]  # type: ignore
            lg.debug(f'Requirement found at {start}-{end}')
            rich.print(req)

        return [], []


def create_grammar():
    req_begin = pp.Suppress(pp.CaselessLiteral('[REQ]'))
    braket_begin = pp.Suppress(pp.Literal('['))
    braket_end = pp.Suppress(pp.Literal(']'))
    field_id = pp.Word(pp.alphas, pp.alphanums + '_')
    field_marker = braket_begin + field_id + braket_end
    field_marker.setParseAction(lambda tokens: str(tokens[0]).lower())  # type: ignore
    yaml_begin = pp.Suppress(pp.Literal('```yaml'))
    yaml_end = pp.Suppress(pp.Literal('```'))
    yaml_content = pp.SkipTo(yaml_end)
    yaml_content.setParseAction(lambda tokens: str(tokens[0]))  # type: ignore
    yaml_block = yaml_begin + yaml_content + yaml_end
    yaml_block.setParseAction(lambda tokens: {'yaml': tokens[0]})  # type: ignore
    content = pp.SkipTo(field_marker | yaml_begin)
    content.setParseAction(lambda tokens: {'text': str(tokens[0])})  # type: ignore
    field = field_marker + content
    field.setParseAction(lambda tokens: {
        'field': {
            'marker': tokens[0],
            'content': tokens[1]
        }
    })  # type: ignore
    fields = pp.ZeroOrMore(field)
    fields.setParseAction(lambda tokens: {'list': list(tokens)})  # type: ignore
    req = req_begin + content + fields + yaml_block
    req.setParseAction(lambda tokens: {
        'req': {
            'content': tokens[0],
            'fields': tokens[1],
            'yaml': tokens[2]
        }
    })  # type: ignore
    return req
