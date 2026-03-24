# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-03-22
# Description: Base class for extracting artifacts from Markdown content.

from pathlib import Path
import logging as lg
import re
from typing import Callable
from lark import Lark, Transformer, exceptions
from benedict import benedict

from syntagmax.extractors.extractor import Extractor, ExtractorResult
from syntagmax.config import Config, InputRecord
from syntagmax.artifact import ArtifactBuilder, Artifact, Location, UNDEFINED_ID


class MarkdownArtifact(Artifact):
    def __init__(self, config: Config):
        super().__init__(config)
        self.yaml_data: benedict | None = None
        self.source_metadata: dict[str, str] = {}


class MarkdownTransformer(Transformer):
    def AID(self, t):
        return str(t).lower()

    def yaml_content(self, t):
        return str(t[0])

    def yaml_block(self, t):
        return {'text': str(t[0]) if t else ''}

    def contents(self, t):
        return {'text': ''.join(str(c) for c in t) if t else ''}

    def field(self, t):
        # field: _LSQB AID _RSQB [FIELD_TEXT] _NL
        # children: AID, [FIELD_TEXT]
        marker = str(t[0])
        text = ''
        if len(t) > 1:
            text = str(t[1])
        return {'field': {'marker': marker, 'contents': {'text': text.strip()}}}

    def fields(self, t):
        return {'list': list(t)}

    def _NL(self, t):
        return None

    def req(self, t):
        # req: _REQ_BEGIN (contents | field)* yaml_block
        # children: (contents | field)* yaml_block
        all_contents = []
        all_fields = []
        yaml_data = t[-1]

        for child in t[:-1]:
            if 'text' in child:
                all_contents.append(child['text'])
            elif 'field' in child:
                all_fields.append(child)

        return {
            'req': {
                'contents': {'text': ''.join(all_contents)},
                'fields': {'list': all_fields},
                'yaml': yaml_data,
            }
        }


class MarkdownExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord, metamodel: dict | None = None):
        super().__init__(config, record, metamodel)
        grammar_path = Path(__file__).parent / 'markdown.lark'
        self._parser = Lark.open(grammar_path, rel_to=__file__, parser='lalr', maybe_placeholders=False)
        self._transformer = MarkdownTransformer()

    def update_artifacts(self, loc_file: str, updates: list[tuple[Artifact, str]]):
        from syntagmax.artifact import LineLocation

        # Read the file
        filepath = self._config.base_dir() / loc_file
        text = filepath.read_text(encoding='utf-8')
        lines = text.splitlines(keepends=True)

        # Apply updates in reverse order of line numbers to avoid offset shifts
        updates.sort(key=lambda u: u[0].location.loc_lines[0], reverse=True)  # type: ignore

        for artifact, new_id in updates:
            if not isinstance(artifact.location, LineLocation):
                continue

            start_line, end_line = artifact.location.loc_lines
            segment_lines = lines[start_line - 1 : end_line]
            segment = ''.join(segment_lines)

            # Shortcut approach:
            # - do not try to manipulate artifact's body
            # - add/update id attribute in the yaml_data dict
            # - re-emit a full yaml block

            if isinstance(artifact, MarkdownArtifact) and artifact.yaml_data is not None:
                yaml_data = artifact.yaml_data
                if yaml_data.get('attrs') is None:
                    yaml_data['attrs'] = {}

                yaml_data['attrs']['id'] = new_id

                # Re-emit YAML
                new_yaml_content = yaml_data.to_yaml()
                new_yaml_block = f'```yaml\n{new_yaml_content.strip()}\n```'

                # Replace the YAML block in the segment
                yaml_start = segment.find('```yaml')
                if yaml_start != -1:
                    yaml_end = segment.find('```', yaml_start + 7)
                    if yaml_end != -1:
                        segment = segment[:yaml_start] + new_yaml_block + segment[yaml_end + 3 :]
            else:
                # Fallback to old method if no yaml_data
                # Update [id] format
                segment = re.sub(r'\[id\]\s*[a-zA-Z0-9-{}:]*', f'[id] {new_id}', segment, flags=re.IGNORECASE)

                # Update YAML block
                yaml_start = segment.find('```yaml')
                if yaml_start != -1:
                    yaml_end = segment.find('```', yaml_start + 7)
                    if yaml_end != -1:
                        yaml_block = segment[yaml_start : yaml_end + 3]
                        # Specific regex for id replacement in YAML to be more robust
                        yaml_block = re.sub(r'^(\s*id:\s*).*$', rf'\g<1>{new_id}', yaml_block, flags=re.MULTILINE)
                        segment = segment[:yaml_start] + yaml_block + segment[yaml_end + 3 :]

            # Replace the segment in the lines list
            lines[start_line - 1 : end_line] = [segment]

        filepath.write_text(''.join(lines), encoding='utf-8')

    def update_artifact(self, artifact: Artifact, fields: dict[str, str]):
        from syntagmax.artifact import LineLocation

        if not isinstance(artifact.location, LineLocation):
            return

        if 'id' in fields:
            self.update_artifacts(artifact.location.loc_file, [(artifact, fields['id'])])

    def _extract_from_markdown(
        self, filepath: Path, markdown: str, location_builder: Callable[[int, int], Location]
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
            end_line = markdown.count('\n', 0, segment_end) + 1

            lg.debug(f'Found requirement at line {start_line}, parsing')

            try:
                tree = self._parser.parse(segment)
                req_data = self._transformer.transform(tree)
                req = benedict(req_data)

                contents = req.get_str('req.contents.text')
                fields = req.get_list('req.fields.list')
                yaml_text = req.get('req.yaml.text')

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

                yaml_attrs = yaml_dict.get_dict('attrs')

                # Merged dict for ID/AType extraction, YAML takes precedence
                temp_attrs = {
                    **{field.get_str('field.marker'): field.get_str('field.contents.text').strip() for field in fields},
                    **yaml_attrs,
                }

                aid = temp_attrs.get('id')

                if not aid:
                    error = f'Missing ID in metadata at line {start_line}'
                    lg.warning(error)
                    pos = segment_end
                    aid = UNDEFINED_ID

                atype = temp_attrs.get('atype') or self._record.default_atype

                builder = ArtifactBuilder(
                    config=self._config,
                    ArtifactClass=MarkdownArtifact,
                    driver=self.driver(),
                    location=location_builder(start_line, end_line),
                    metamodel=self._metamodel,
                )

                builder.add_id(aid, atype)
                builder.add_field('id', aid)

                # Add fields found in markdown individually
                for field in fields:
                    marker = field.get_str('field.marker')
                    if marker.lower() in ['id', 'atype']:
                        continue
                    builder.add_field(marker, field.get_str('field.contents.text').strip())

                # Add fields found in YAML individually
                for name, value in yaml_attrs.items():
                    if name.lower() in ['id', 'atype']:
                        continue
                    if isinstance(value, list):
                        for v in value:
                            builder.add_field(name, str(v))
                    else:
                        builder.add_field(name, str(value))

                # Add contents as a field
                builder.add_field('contents', contents)

                artifact = builder.build()
                if isinstance(artifact, MarkdownArtifact):
                    artifact.yaml_data = yaml_dict
                    # Record source for each field
                    for field in fields:
                        artifact.source_metadata[field.get_str('field.marker').lower()] = 'markdown'
                    for name in yaml_attrs.keys():
                        artifact.source_metadata[name.lower()] = 'yaml'

                artifacts.append(artifact)

            except (exceptions.ParseError, exceptions.UnexpectedToken) as e:
                lg.exception(e)
                error = f'Parse error in requirement at line {start_line} in {filepath}'
                errors.append(error)

            except Exception as e:
                lg.exception(e)
                error = f'Error processing requirement at line {start_line} in {filepath}'
                errors.append(error)

            pos = segment_end

        return artifacts, errors
