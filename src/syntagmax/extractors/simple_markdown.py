# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-25
# Description: Extracts artifacts from standalone markdown files with YAML frontmatter.

import re
import logging as lg
from pathlib import Path

import yaml

from syntagmax.config import Config, InputRecord
from syntagmax.artifact import ArtifactBuilder, Artifact, FileLocation, ValidationError
from syntagmax.extractors.extractor import Extractor
from syntagmax.blocks import Block, ArtifactBlock, ErrorBlock
from syntagmax.i18n import _


_FRONTMATTER_RE = re.compile(
    r'^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n(.*))?$',
    re.DOTALL,
)


def _pop_case_insensitive(data: dict, key: str, default):
    """Pop a key from a dict using case-insensitive matching."""
    if key in data:
        return data.pop(key)
    for k in list(data.keys()):
        if k.lower() == key.lower():
            return data.pop(k)
    return default


class SimpleMarkdownExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord, metamodel: dict | None = None):
        super().__init__(config, record, metamodel)

    def driver(self) -> str:
        return 'simple-markdown'

    def _parse_frontmatter(self, text: str) -> tuple[dict | None, str]:
        """Parse YAML frontmatter from markdown text.

        Returns (frontmatter_dict, body) if valid frontmatter is found.
        Returns (None, text) if no frontmatter or non-dict YAML.
        Re-raises yaml.YAMLError on malformed YAML.
        """
        match = _FRONTMATTER_RE.match(text)

        if not match:
            return (None, text)

        data = yaml.safe_load(match.group(1))

        if not isinstance(data, dict):
            lg.warning(f'{self.driver()} :: Frontmatter is not a YAML dictionary, treating as no frontmatter')
            return (None, text)

        body = match.group(2) if match.group(2) is not None else ''
        return (data, body)

    def _roundtrip_frontmatter(self, text: str) -> tuple:
        """Parse frontmatter using ruamel.yaml for round-trip editing.

        Returns (data: CommentedMap, body: str, newline: str) or raises.
        """
        from ruamel.yaml import YAML as RuamelYAML
        from ruamel.yaml.comments import CommentedMap

        match = _FRONTMATTER_RE.match(text)
        newline = '\r\n' if '\r\n' in text else '\n'

        if not match:
            # No frontmatter — create empty one
            return CommentedMap(), text, newline

        raw_yaml = match.group(1)
        body = match.group(2) if match.group(2) is not None else ''

        ryaml = RuamelYAML(typ='rt')
        ryaml.preserve_quotes = True
        data = ryaml.load(raw_yaml)

        if data is None:
            data = CommentedMap()
        elif not isinstance(data, dict):
            data = CommentedMap()

        return data, body, newline

    def _serialize_frontmatter(self, data, body: str, newline: str) -> str:
        """Serialize a CommentedMap back into a full markdown file."""
        from ruamel.yaml import YAML as RuamelYAML
        from ruamel.yaml.compat import StringIO

        ryaml = RuamelYAML(typ='rt')
        ryaml.preserve_quotes = True
        stream = StringIO()
        ryaml.dump(data, stream)
        yaml_text = stream.getvalue()

        # Remove trailing newline added by ruamel
        if yaml_text.endswith('\n'):
            yaml_text = yaml_text[:-1]

        parts = [f'---{newline}', yaml_text, f'{newline}---{newline}']
        if body:
            parts.append(body)
            if not body.endswith('\n') and not body.endswith('\r\n'):
                parts.append(newline)

        return ''.join(parts)

    def update_artifacts(self, loc_file: str, updates: list[tuple[Artifact, str]]):
        """Renumber artifact IDs in a simple-markdown file.

        Each file contains exactly one artifact, so updates list has at most one entry
        per file. The ID is updated in the YAML frontmatter.
        """
        filepath = self._config.base_dir() / loc_file
        text = filepath.read_text(encoding='utf-8')

        for artifact, new_id in updates:
            data, body, newline = self._roundtrip_frontmatter(text)

            # Update or insert the id key (case-insensitive find)
            existing_key = None
            for k in data:
                if k.lower() == 'id':
                    existing_key = k
                    break

            if existing_key:
                data[existing_key] = new_id
            else:
                # Insert id at the top
                from ruamel.yaml.comments import CommentedMap
                new_data = CommentedMap()
                new_data['id'] = new_id
                new_data.update(data)
                data = new_data

            text = self._serialize_frontmatter(data, body, newline)

        filepath.write_text(text, encoding='utf-8')

    def update_artifact_attributes(
        self,
        loc_file: str,
        updates: list[tuple[Artifact, dict[str, 'str | None'], str]],
        target_type: str = 'attr',
    ) -> str:
        """Apply attribute updates to the YAML frontmatter.

        For simple-markdown, target_type is always 'attr' (YAML frontmatter).
        Inline [FIELD] markers are not used by this driver.

        Returns the modified file content as a string (for atomic writes).
        """
        if target_type != 'attr':
            raise NotImplementedError(
                f'Driver "{self.driver()}" only supports target_type="attr" (YAML frontmatter)'
            )

        filepath = self._config.base_dir() / loc_file
        text = filepath.read_text(encoding='utf-8')

        for artifact, attrs_delta, operation in updates:
            data, body, newline = self._roundtrip_frontmatter(text)

            for attr_name, attr_value in attrs_delta.items():
                if operation == 'add':
                    # Only add if not already present
                    if attr_name not in data:
                        data[attr_name] = attr_value
                elif operation == 'del':
                    # Remove if present (case-insensitive)
                    key_to_remove = None
                    for k in data:
                        if k.lower() == attr_name.lower():
                            key_to_remove = k
                            break
                    if key_to_remove:
                        del data[key_to_remove]
                elif operation == 'replace':
                    if attr_value is not None:
                        # Find existing key (case-insensitive) or use given name
                        existing_key = None
                        for k in data:
                            if k.lower() == attr_name.lower():
                                existing_key = k
                                break
                        if existing_key:
                            data[existing_key] = attr_value
                        else:
                            data[attr_name] = attr_value
                    else:
                        # value=None means deletion
                        key_to_remove = None
                        for k in data:
                            if k.lower() == attr_name.lower():
                                key_to_remove = k
                                break
                        if key_to_remove:
                            del data[key_to_remove]

            text = self._serialize_frontmatter(data, body, newline)

        return text

    def extract_blocks_from_file(self, filepath: Path) -> list[Block]:
        text = filepath.read_text(encoding='utf-8-sig')

        if not text:
            return []

        try:
            frontmatter, body = self._parse_frontmatter(text)
        except yaml.YAMLError as e:
            msg = _("{driver} :: Malformed YAML frontmatter in {file}: {error}").format(driver=self.driver(), file=filepath, error=str(e))
            return [ErrorBlock(message=msg, raw_text=text)]

        if frontmatter is None:
            frontmatter = {}

        aid = str(_pop_case_insensitive(frontmatter, 'id', filepath.stem))
        atype = str(_pop_case_insensitive(frontmatter, 'atype', self._record.default_atype))

        location = FileLocation(self._config.derive_path(filepath))

        builder = ArtifactBuilder(
            self._config, Artifact, self.driver(), location, self._metamodel, record=self._record
        )

        try:
            builder.add_id(aid, atype)
            builder.add_field('id', aid)

            for key, value in frontmatter.items():
                if value is None:
                    continue
                if isinstance(value, list):
                    for v in value:
                        if v is None:
                            continue
                        builder.add_field(key, self._yaml_value_to_str(v, atype, key))
                else:
                    builder.add_field(key, self._yaml_value_to_str(value, atype, key))

            builder.add_field('contents', body.strip())

            artifact = builder.build()
            return [ArtifactBlock(artifact=artifact, raw_text=text)]

        except ValidationError as e:
            return [ErrorBlock(message=str(e), raw_text=text)]
