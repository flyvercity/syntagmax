# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from Obsidian files
import json
from pathlib import Path
import logging as lg
import re

from lark import Lark, Transformer, exceptions
from benedict import benedict

from syntagmax.extractors.extractor import Extractor, ExtractorResult
from syntagmax.config import Config, InputRecord
from syntagmax.artifact import ArtifactBuilder, Artifact, LineLocation


class ObsidianArtifact(Artifact):
    def __init__(self, config: Config):
        super().__init__(config)


class ObsidianTransformer(Transformer):
    def AID(self, t):
        return str(t).lower()

    def content_text(self, t):
        return str(t[0])

    def yaml_content(self, t):
        return str(t[0])

    def yaml_block(self, t):
        return {'text': str(t[0]) if t else ""}

    def content(self, t):
        return {'text': str(t[0]) if t else ""}

    def field(self, t):
        return {
            'field': {
                'marker': t[0],
                'content': t[1]
            }
        }

    def fields(self, t):
        return {'list': list(t)}

    def req(self, t):
        return {
            'req': {
                'content': t[0],
                'fields': t[1],
                'yaml': t[2]
            }
        }


class ObsidianExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord):
        super().__init__(config, record)
        grammar_path = Path(__file__).parent / 'obsidian.lark'
        self._parser = Lark.open(
            grammar_path,
            rel_to=__file__,
            parser='lalr',
            maybe_placeholders=False
        )
        self._transformer = ObsidianTransformer()

    def driver(self) -> str:
        return 'obsidian'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        markdown = filepath.read_text(encoding='utf-8')
        return self._extract_from_markdown(filepath, markdown)

    def _extract_from_markdown(
        self, filepath: Path, markdown: str
    ) -> ExtractorResult:
        artifacts: list[Artifact] = []
        errors: list[str] = []

        # Find all [REQ] segments manually
        start_marker = re.compile(r'\[REQ\]', re.IGNORECASE)
        pos = 0

        while True:
            match = start_marker.search(markdown, pos)

            if not match:
                break

            start_pos = match.start()

            # Find the end marker of the YAML block
            yaml_end_marker = '```'
            yaml_start_pos = markdown.find('```yaml', start_pos)

            if yaml_start_pos == -1:
                # No YAML block, skip or report error
                pos = match.end()
                continue

            end_pos = markdown.find(yaml_end_marker, yaml_start_pos + 7)

            if end_pos == -1:
                # Malformed YAML block
                pos = yaml_start_pos + 7
                continue

            segment_end = end_pos + len(yaml_end_marker)
            segment = markdown[start_pos:segment_end]
            start_line = markdown.count('\n', 0, start_pos) + 1

            lg.debug(f'Found requirement at line {start_line}, parsing')

            try:
                tree = self._parser.parse(segment)
                req_data = self._transformer.transform(tree)
                req = benedict(req_data)

                content = req.get_str('req.content.text')
                lg.debug(f'Content: {content}')
                fields = req.get_list('req.fields.list')
                lg.debug(f'Fields: {fields}')
                yaml_text = req.get('req.yaml.text')
                lg.debug(f'YAML text: {yaml_text}')

                if not yaml_text:
                    error = f'Missing YAML in metadata at line {start_line}'
                    lg.error(error)
                    errors.append(error)
                    pos = segment_end
                    continue

                yaml_dict = benedict.from_yaml(yaml_text)

                if 'attrs' not in yaml_dict:
                    error = f'Invalid metadata in YAML at line {start_line}'
                    lg.error(error)
                    errors.append(error)
                    pos = segment_end
                    continue

                attrs = benedict({
                    field.get_str('field.marker'): field.get_str('field.content.text')
                    for field in fields
                })

                attrs.update(yaml_dict.get_dict('attrs'))
                attrs['content'] = content

                builder = ArtifactBuilder(
                    config=self._config,
                    ArtifactClass=ObsidianArtifact,
                    driver=self.driver(),
                    location=LineLocation(
                        loc_file=self._config.derive_path(filepath),
                        loc_lines=(start_line, segment_end)
                    )
                )

                pid_handle = attrs.get_str('pid')

                if pid_handle and pid_handle != 'None':
                    pid_split = pid_handle.split(':')

                    if len(pid_split) != 2:
                        error = f'Invalid PID: {pid_handle}'
                        lg.error(error)
                        errors.append(error)
                    else:
                        p_atype = pid_split[0]
                        p_aid = pid_split[1]
                        builder.add_pid(p_aid, p_atype)

                aid = attrs.get('id')

                if not aid:
                    error = f'Missing ID in metadata at line {start_line}'
                    lg.error(error)
                    errors.append(error)
                    pos = segment_end
                    continue

                atype = attrs.get('atype') or self._record.default_atype
                builder.add_id(aid, atype)
                builder.add_fields(attrs)
                artifacts.append(builder.build())

            except (exceptions.ParseError, exceptions.UnexpectedToken) as e:
                error = f'Parse error in Obsidian requirement at line {start_line}: {e}'
                lg.error(error)
                errors.append(error)

            except Exception as e:
                error = f'Error processing Obsidian requirement at line {start_line}: {e}'
                lg.error(error)
                errors.append(error)

            pos = segment_end

        return artifacts, errors
