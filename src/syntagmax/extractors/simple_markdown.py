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

    def extract_blocks_from_file(self, filepath: Path) -> list[Block]:
        text = filepath.read_text(encoding='utf-8-sig')

        if not text:
            return []

        try:
            frontmatter, body = self._parse_frontmatter(text)
        except yaml.YAMLError as e:
            msg = f'{self.driver()} :: Malformed YAML frontmatter in {filepath}: {e}'
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
                        builder.add_field(key, str(v))
                else:
                    builder.add_field(key, str(value))

            builder.add_field('contents', body.strip())

            artifact = builder.build()
            return [ArtifactBlock(artifact=artifact, raw_text=text)]

        except ValidationError as e:
            return [ErrorBlock(message=str(e), raw_text=text)]
