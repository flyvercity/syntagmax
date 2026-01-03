# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from markdown files.

import logging as lg
import traceback
import yaml
from typing import Generator, Any
from pathlib import Path

from syntagmax.extractors.extractor import Extractor, ExtractorResult
from syntagmax.config import Config
from syntagmax.artifact import ArtifactBuilder, Artifact


class MarkdownExtractor(Extractor):
    def __init__(self, config: Config):
        self._config = config

    def driver(self) -> str:
        return 'markdown'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        try:
            markdown = filepath.read_text(encoding='utf-8')
            base_dir = self._config.base_dir()
            location = f'file://{filepath.relative_to(base_dir)}'
            return self._extract_from_markdown(location, markdown)

        except Exception as e:
            if self._config.params['verbose']:
                lg.error(f'Error extracting from {filepath}: {e}, {traceback.format_exc()}')

            message = f'Error extracting from {filepath}: {e}'
            return [], [message]

    def _extract_from_markdown(self, location: str, markdown: str) -> ExtractorResult:
        artifacts: list[Artifact] = []
        errors: list[str] = []

        lines = markdown.split('\n')

        for block in self._next_code_block(lines):
            block_yaml = yaml.safe_load('\n'.join(block))
            lg.debug(f'YAML block found: {block_yaml}')

            metadata = block_yaml.get('syntagmax', {})

            if not metadata:
                continue

            try:
                if artifacts:
                    errors.append(f'Multiple artifacts found at {location}')
                    continue

                builder = ArtifactBuilder(
                    config=self._config,
                    ArtifactClass=Artifact,
                    driver=self.driver(),
                    location=location
                )

                if handle := metadata.get('id'):
                    if not isinstance(handle, str):
                        errors.append(f'Invalid handle: {handle}')
                        continue

                    [atype, aid] = self._split_handle(handle)
                    builder.add_id(aid, atype)

                if pids := metadata.get('pid'):
                    self._extract_pid(pids, builder, errors)

                if desc := metadata.get('desc'):
                    builder.add_desc(desc)

                artifacts.append(builder.build())
            except Exception as e:
                errors.append(f'Error extracting from {location}: {e}')

        return artifacts, errors

    def _extract_pid(self, pids: Any, builder: ArtifactBuilder, errors: list[str]) -> None:
        if pids == 'None':
            return

        if not isinstance(pids, list):
            errors.append(f'Invalid PIDs: {pids}')
            return

        for pid in pids:  # type: ignore
            if not isinstance(pid, str):
                errors.append(f'Invalid PID: {pid}')
                continue

            [atype, aid] = self._split_handle(pid)
            builder.add_pid(aid, atype)

    def _next_code_block(self, lines: list[str]) -> Generator[list[str]]:
        block: list[str] | None = None
        capture = False

        for line in lines:
            if line.startswith('```yaml'):
                capture = True
                continue

            if line.startswith('```'):
                capture = False

                if block:
                    yield block

                block = None

            if capture:
                if block is None:
                    block = []

                block.append(line)
