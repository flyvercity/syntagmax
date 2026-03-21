# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Extracts artifacts from sidecar YAML files.

import logging as lg
from pathlib import Path
import yaml

from syntagmax.config import Config, InputRecord
from syntagmax.artifact import ArtifactBuilder, Artifact, FileLocation, ValidationError
from syntagmax.extractors.extractor import Extractor, ExtractorResult


class SidecarExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord, metamodel: dict | None = None):
        super().__init__(config, record, metamodel)

    def driver(self) -> str:
        return 'sidecar'

    def extract(self) -> ExtractorResult:
        artifacts, errors = super().extract()

        # Check for orphaned sidecar files in the input record's base directory
        record_base = self._record.record_base

        if record_base and record_base.exists():
            for sidecar_path in list(record_base.rglob('*.stmx')) + list(record_base.rglob('*.syntagmax')):
                original_name = sidecar_path.name

                if original_name.endswith('.stmx'):
                    original_name = original_name[:-5]
                elif original_name.endswith('.syntagmax'):
                    original_name = original_name[:-10]

                original_path = sidecar_path.with_name(original_name)

                if not original_path.exists():
                    errors.append(f'{self.driver()} :: Orphaned sidecar file {sidecar_path} without matching original file')

        return artifacts, errors

    def extract_from_file(self, filepath: Path) -> ExtractorResult:
        lg.debug(f'Processing sidecar driver for original file: {filepath}')

        stmx_path = filepath.with_name(f"{filepath.name}.stmx")
        syntagmax_path = filepath.with_name(f"{filepath.name}.syntagmax")

        stmx_exists = stmx_path.exists()
        syntagmax_exists = syntagmax_path.exists()

        if stmx_exists and syntagmax_exists:
            return [], [f'{self.driver()} :: Both .stmx and .syntagmax sidecars are present for {filepath}']

        if not stmx_exists and not syntagmax_exists:
            return [], [f'{self.driver()} :: Missing sidecar file for {filepath}']

        sidecar_path = stmx_path if stmx_exists else syntagmax_path

        try:
            with open(sidecar_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return [], [f'{self.driver()} :: Malformed YAML in sidecar {sidecar_path}: {e}']
        except Exception as e:
            return [], [f'{self.driver()} :: Could not read sidecar {sidecar_path}: {e}']

        if not isinstance(data, dict):
            return [], [f'{self.driver()} :: Sidecar {sidecar_path} does not contain a valid YAML dictionary']

        if 'id' not in data:
            return [], [f'{self.driver()} :: Missing required "id" field in sidecar {sidecar_path}']

        aid = str(data.pop('id'))
        atype = str(data.pop('atype', self._record.default_atype))

        location = FileLocation(self._config.derive_path(filepath))

        builder = ArtifactBuilder(
            self._config, Artifact, self.driver(), location, self._metamodel
        )

        try:
            builder.add_id(aid, atype)
            builder.add_field('id', aid)

            for key, value in data.items():
                if isinstance(value, list):
                    for v in value:
                        builder.add_field(key, v)
                else:
                    builder.add_field(key, value)

            return [builder.build()], []

        except ValidationError as e:
            return [], [f'{self.driver()} :: Validation error in {sidecar_path}: {e}']
