# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from Obsidian files
from pathlib import Path
import logging as lg

import pyparsing as pp
from benedict import benedict

from syntagmax.extractors.extractor import Extractor, ExtractorResult
from syntagmax.config import Config, InputRecord
from syntagmax.artifact import ArtifactBuilder, Artifact, LineLocation


class ObsidianArtifact(Artifact):
    def __init__(self, config: Config):
        super().__init__(config)


class ObsidianExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord):
        super().__init__(config, record)

    def driver(self) -> str:
        return 'obsidian'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        markdown = filepath.read_text(encoding='utf-8')
        return self._extract_from_markdown(filepath, markdown)

    def _extract_from_markdown(
        self, filepath: Path, markdown: str
    ) -> ExtractorResult:
        req_grammar = create_grammar()
        req_match = req_grammar.scan_string(markdown)

        artifacts: list[Artifact] = []
        errors: list[str] = []

        for (match, start, end) in req_match:
            if len(match) != 1:
                errors.append(f'Expected 1 match, got {len(match)}')
                continue

            req = benedict(match[0])
            lg.debug(f'Requirement found at {start}-{end}: {req}')

            content = req.get_str('req.content.text')
            lg.debug(f'Content: {content}')
            fields = req.get_list('req.fields.list')
            lg.debug(f'Fields: {fields}')
            yaml_text = req.get('req.yaml.text')
            lg.debug(f'YAML text: {yaml_text}')

            if not yaml_text:
                error = f'Missing YAML in metadata: {yaml_text}'
                lg.error(error)
                errors.append(error)
                continue

            if self._config.params['verbose']:
                lg.debug(f'YAML content: {yaml_text}')

            yaml_dict = benedict.from_yaml(yaml_text)

            if 'attrs' not in yaml_dict:
                error = f'Invalid metadata in YAML: {yaml_text}'
                lg.error(error)
                errors.append(error)
                continue

            attrs = {
                field.get_str('field.marker'): field.get_str('field.content.text')
                for field in fields
            }

            attrs.update(yaml_dict.get_dict('attrs'))
            attrs['content'] = content

            builder = ArtifactBuilder(
                config=self._config,
                ArtifactClass=ObsidianArtifact,
                driver=self.driver(),
                location=LineLocation(filepath, (start, end))
            )

            id = attrs.get('id')

            if not id:
                error = f'Missing ID in metadata: {yaml_text}'
                lg.error(error)
                errors.append(error)
                continue

            atype = attrs.get('atype') or self._record['default_atype']
            builder.add_id(id, atype)
            builder.add_fields(attrs)
            artifacts.append(builder.build())

        return artifacts, errors


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
    yaml_block.setParseAction(lambda tokens: {'text': tokens[0]})  # type: ignore
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
