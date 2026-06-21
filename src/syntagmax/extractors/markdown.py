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
from syntagmax.blocks import Block, TextBlock, ArtifactBlock, ErrorBlock


class MarkdownArtifact(Artifact):
    def __init__(self, config: Config):
        super().__init__(config)
        self.yaml_data: benedict | None = None
        self.source_metadata: dict[str, str] = {}


class MarkdownTransformer(Transformer):
    def AID(self, t):
        return str(t).lower()

    def yaml_block(self, t):
        # yaml_block: _YAML_BEGIN [YAML_CONTENT] _YAML_END
        # children: [YAML_CONTENT]
        return {'text': str(t[0]) if t else '', 'type': 'yaml'}

    def terminator(self, t):
        # terminator: yaml_block | _REQ_END
        # If yaml_block matches, t[0] is its result.
        # If _REQ_END matches, t is empty because _ tokens are ignored.
        if not t:
            return {'type': 'slash_req'}
        return t[0]

    def contents(self, t):
        return {'text': ''.join(str(c) for c in t) if t else ''}

    def field(self, t):
        # field: _LSQB AID _RSQB [FIELD_TEXT] _NL FIELD_CONT*
        # children: AID, [FIELD_TEXT], [FIELD_CONT...]
        marker = str(t[0])
        parts = [str(c).strip() for c in t[1:] if str(c).strip()]
        text = '\n'.join(parts)
        return {'field': {'marker': marker, 'contents': {'text': text}}}

    def _NL(self, t):
        return None

    def req(self, t):
        # req: _REQ_BEGIN _NL? [contents] field* terminator
        # children: [contents], field*, terminator
        contents_text = ''
        all_fields = []
        terminator = t[-1]

        for child in t[:-1]:
            if isinstance(child, dict):
                if 'text' in child:
                    contents_text = child['text']
                elif 'field' in child:
                    all_fields.append(child)

        return {
            'req': {
                'contents': {'text': contents_text},
                'fields': {'list': all_fields},
                'yaml': terminator if terminator.get('type') == 'yaml' else None,
            }
        }


class MarkdownExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord, metamodel: dict | None = None):
        super().__init__(config, record, metamodel)
        grammar_path = Path(__file__).parent / 'markdown.lark'
        grammar = grammar_path.read_text(encoding='utf-8')

        # Replace placeholders with actual marker
        marker = self._record.marker
        grammar = grammar.replace('_TOKEN_BEGIN', f'"[{marker}]"i')
        grammar = grammar.replace('_TOKEN_END', f'"[/{marker}]"i')

        self._parser = Lark(grammar, parser='lalr', maybe_placeholders=False)
        self._transformer = MarkdownTransformer()

    def _is_multiple_attr(self, atype: str, attr_name: str) -> bool:
        if not self._metamodel:
            return False
        attrs = self._metamodel.get('artifacts', {}).get(atype, {}).get('attributes', {}).get(attr_name, [])
        if isinstance(attrs, dict):
            attrs = [attrs]
        return any(rule.get('multiple', False) for rule in attrs)

    def update_artifacts(self, loc_file: str, updates: list[tuple[Artifact, str]]):
        from syntagmax.artifact import LineLocation

        # Read the file
        filepath = self._config.base_dir() / loc_file
        text = filepath.read_text(encoding='utf-8')
        lines = text.splitlines(keepends=True)

        # Apply updates in reverse order of line numbers to avoid offset shifts
        updates.sort(key=lambda u: u[0].location.loc_lines[0], reverse=True)  # type: ignore

        marker = self._record.marker

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

            if isinstance(artifact, MarkdownArtifact) and artifact.yaml_data is not None and ('attrs' in artifact.yaml_data or artifact.yaml_data):
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
                    # No yaml block found but we have yaml_data?
                    # This could happen if it was terminated by [/{marker}] and we want to ADD YAML.
                    # For now, let's append before [/{marker}] if it exists, or at the end.
                    slash_req_pos = segment.rfind(f'[/{marker}]')
                    if slash_req_pos != -1:
                        segment = segment[:slash_req_pos] + '\n' + new_yaml_block + '\n' + segment[slash_req_pos:]
                    else:
                        segment = segment.strip() + '\n\n' + new_yaml_block + '\n'

                # Also update [id] format if it exists in the markdown
                segment = re.sub(r'\[id\]\s*[a-zA-Z0-9_{}:-]*', f'[id] {new_id}', segment, flags=re.IGNORECASE)
            else:
                # Fallback to old method if no yaml_data
                # Update [id] format
                segment = re.sub(r'\[id\]\s*[a-zA-Z0-9_{}:-]*', f'[id] {new_id}', segment, flags=re.IGNORECASE)

                # Update YAML block if exists
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

    def _extract_from_markdown(self, filepath: Path, markdown: str, location_builder: Callable[[int, int], Location]) -> ExtractorResult:
        blocks = self._extract_blocks_from_markdown(filepath, markdown, location_builder)
        artifacts = [b.artifact for b in blocks if isinstance(b, ArtifactBlock)]
        errors = [b.message for b in blocks if isinstance(b, ErrorBlock)]
        return artifacts, errors

    def _extract_blocks_from_markdown(self, filepath: Path, markdown: str, location_builder: Callable[[int, int], Location] | None = None) -> list[Block]:
        from syntagmax.artifact import LineLocation

        blocks: list[Block] = []
        marker = self._record.marker
        start_marker_re = re.compile(rf'\[{marker}\]', re.IGNORECASE)
        pos = 0

        if location_builder is None:
            loc_file = self._config.derive_path(filepath)

            def location_builder(start, end):
                return LineLocation(loc_file=loc_file, loc_lines=(start, end))

        while True:
            match = start_marker_re.search(markdown, pos)
            if not match:
                break

            start_pos = match.start()

            # Capture text before this segment
            text_before = markdown[pos:start_pos]
            if text_before:
                blocks.append(TextBlock(content=text_before))

            # Find segment end
            yaml_start_pos = markdown.find('```yaml', start_pos)
            slash_req_match = re.search(rf'\[/{marker}\]', markdown[start_pos:], re.IGNORECASE)
            slash_req_pos = (start_pos + slash_req_match.start()) if slash_req_match else -1
            segment_end = -1

            if yaml_start_pos != -1 and (slash_req_pos == -1 or yaml_start_pos < slash_req_pos):
                end_pos = markdown.find('```', yaml_start_pos + 7)
                if end_pos != -1:
                    segment_end = end_pos + 3
            elif slash_req_pos != -1:
                segment_end = slash_req_pos + len(f'[/{marker}]')

            if segment_end == -1:
                start_line = markdown.count('\n', 0, start_pos) + 1
                if yaml_start_pos != -1:
                    error = f'Unclosed YAML block in requirement at line {start_line} in {filepath}'
                else:
                    error = f'Unterminated requirement at line {start_line} in {filepath}'
                lg.error(error)
                raw = markdown[start_pos : match.end()]
                blocks.append(ErrorBlock(message=error, raw_text=raw))
                pos = match.end()
                continue

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
                yaml_info = req.get('req.yaml')
                yaml_text = yaml_info.get('text') if yaml_info else None

                # NBSP detection
                if '\xa0' in segment:
                    error = f'Non-breaking space (NBSP) detected in requirement at line {start_line} in {filepath}'
                    lg.error(error)
                    blocks.append(ErrorBlock(message=error, raw_text=segment))
                    pos = segment_end
                    continue

                if not yaml_text:
                    yaml_dict = benedict({'attrs': {}})
                    yaml_attrs = {}
                else:
                    yaml_dict = benedict.from_yaml(yaml_text)

                    if 'attrs' not in yaml_dict:
                        error = f'Invalid metadata in YAML at line {start_line}'
                        lg.error(error)
                        blocks.append(ErrorBlock(message=error, raw_text=segment))
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

                if 'atype' in temp_attrs:
                    lg.warning(
                        f'Overriding default atype with `atype` attribute in {filepath} at line {start_line}. '
                        'To change the type for all artifacts in this source, use the `atype` setting in config.toml.'
                    )

                atype = temp_attrs.get('atype') or self._record.default_atype

                builder = ArtifactBuilder(
                    config=self._config,
                    ArtifactClass=MarkdownArtifact,
                    driver=self.driver(),
                    location=location_builder(start_line, end_line),
                    metamodel=self._metamodel,
                    record=self._record,
                )

                builder.add_id(aid, atype)
                builder.add_field('id', aid)

                # Add fields found in markdown individually
                for field in fields:
                    field_marker = field.get_str('field.marker')
                    if field_marker.lower() in ['id', 'atype']:
                        continue
                    builder.add_field(field_marker, field.get_str('field.contents.text').strip())

                # Add fields found in YAML individually
                for name, value in yaml_attrs.items():
                    if name.lower() in ['id', 'atype']:
                        continue
                    if value is None:
                        continue
                    if isinstance(value, list):
                        for v in value:
                            builder.add_field(name, str(v))
                    elif self._is_multiple_attr(atype, name) and ',' in str(value):
                        for v in str(value).split(','):
                            builder.add_field(name, v.strip())
                    else:
                        builder.add_field(name, str(value))

                # Add contents as a field
                builder.add_field('contents', contents)

                artifact = builder.build()
                if isinstance(artifact, MarkdownArtifact):
                    artifact.yaml_data = yaml_dict
                    for field in fields:
                        artifact.source_metadata[field.get_str('field.marker').lower()] = 'markdown'
                    for name in yaml_attrs.keys():
                        artifact.source_metadata[name.lower()] = 'yaml'

                blocks.append(ArtifactBlock(artifact=artifact, raw_text=segment))

            except (exceptions.ParseError, exceptions.UnexpectedToken) as e:
                lg.exception(e)
                error = f'Parse error in requirement at line {start_line} in {filepath}'
                blocks.append(ErrorBlock(message=error, raw_text=segment))

            except Exception as e:
                lg.exception(e)
                error = f'Error processing requirement at line {start_line} in {filepath}'
                blocks.append(ErrorBlock(message=error, raw_text=segment))

            pos = segment_end

        # Capture trailing text
        text_after = markdown[pos:]
        if text_after:
            blocks.append(TextBlock(content=text_after))

        return blocks

    def extract_blocks_from_file(self, filepath: Path) -> list[Block]:
        markdown = filepath.read_text(encoding='utf-8')
        return self._extract_blocks_from_markdown(filepath, markdown)
