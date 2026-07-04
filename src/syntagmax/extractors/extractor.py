# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Base class for all extractors.

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Sequence
import logging as lg

from syntagmax.config import InputRecord, Config
from syntagmax.artifact import Artifact

if TYPE_CHECKING:
    from syntagmax.blocks import Block

type ExtractorResult = tuple[Sequence[Artifact], list[str]]


class Extractor:
    def __init__(self, config: Config, record: InputRecord, metamodel: dict | None = None):
        self._config = config
        self._record = record
        self._metamodel = metamodel

    def driver(self) -> str: ...

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        from syntagmax.blocks import ArtifactBlock, ErrorBlock

        blocks = self.extract_blocks_from_file(filepath)
        artifacts = [b.artifact for b in blocks if isinstance(b, ArtifactBlock)]
        errors = [b.message for b in blocks if isinstance(b, ErrorBlock)]
        return artifacts, errors

    def extract(self) -> ExtractorResult:
        errors: list[str] = []
        artifacts: list[Artifact] = []

        for filepath in self._record.filepaths:
            lg.debug(f'Processing file: {filepath}')
            file_artifacts, file_errors = self.extract_from_file(filepath)
            artifacts.extend(file_artifacts)
            errors.extend(file_errors)

            if errors:
                lg.debug(f'Errors were reported for {filepath}')
            else:
                lg.debug(f'Successfully processed file: {filepath}')

        return artifacts, errors

    def extract_blocks_from_file(self, filepath: Path) -> list['Block']:
        return []

    def update_artifact(self, artifact: Artifact, fields: dict[str, str]): ...

    def update_artifacts(self, loc_file: str, updates: list[tuple[Artifact, str]]):
        # Default implementation for bulk updates
        for artifact, new_id in updates:
            self.update_artifact(artifact, {'id': new_id})

    def update_artifact_attributes(
        self,
        loc_file: str,
        updates: list[tuple['Artifact', dict[str, 'str | None'], str]],
        target_type: str = 'attr',
    ) -> str:
        """Apply attribute updates to artifacts in a file. Returns the modified file content.

        Unlike update_artifacts() which writes directly to disk, this method returns
        the modified content as a string to support atomic writes and dry-run without
        side effects.

        Each update is (artifact, {attr_name: value_or_None}, operation).
        operation is 'add', 'del', or 'replace'. value=None means deletion.
        target_type is 'attr' (YAML) or 'field' (inline [FIELD] markers).
        """
        raise NotImplementedError(
            f'Driver "{self._record.driver}" does not support attribute manipulation'
        )
