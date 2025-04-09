# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from markdown files.

import yaml
from typing import Generator
from pathlib import Path

from gitreqms.extractors.extractor import Extractor, ExtractorResult
from gitreqms.config import Params
from gitreqms.artifact import ArtifactBuilder, Artifact

class MarkdownExtractor(Extractor):
    def __init__(self, params: Params):
        self._params: Params = params

    def driver(self) -> str:
        return 'markdown'

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        try:
            markdown = filepath.read_text()
            location = self._format_file_location(filepath)
            return self._extract_from_markdown(location, markdown)
        except Exception as e:
            message = f'Error extracting from {filepath}: {e}'
            return [], [message]

    def _extract_from_markdown(self, location: str, markdown: str) -> ExtractorResult:
        artifacts: list[Artifact] = []
        errors: list[str] = []

        lines = markdown.split('\n')

        for block in self._next_code_block(lines):
            block_yaml = yaml.safe_load('\n'.join(block))
            
            metadata = block_yaml.get('gitreqms', {})

            if not metadata:
                continue

            if artifacts:
                errors.append(f'Multiple artifacts found at {location}')
                continue

            builder = ArtifactBuilder(driver=self.driver(), location=location)

            if handle := metadata.get('id'):
                [atype, aid] = self._split_handle(handle)
                builder.add_id(aid, atype)

            if pids := metadata.get('pid'):
                for pid in pids:
                    [atype, aid] = self._split_handle(pid)
                    builder.add_pid(aid, atype)

            if desc := metadata.get('desc'):
                builder.add_desc(desc)

            artifacts.append(builder.build())

        return artifacts, errors

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
