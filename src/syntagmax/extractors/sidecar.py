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
from syntagmax.artifact import UNDEFINED_ID
from syntagmax.blocks import Block, ArtifactBlock, ErrorBlock
from syntagmax.i18n import _


def _pop_case_insensitive(data: dict, key: str, default):
    """Pop a key from a dict using case-insensitive matching."""
    if key in data:
        return data.pop(key)
    for k in list(data.keys()):
        if k.lower() == key.lower():
            return data.pop(k)
    return default


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
                    errors.append(_("{driver} :: Orphaned sidecar file {path} without matching original file").format(driver=self.driver(), path=sidecar_path))

        return artifacts, errors

    def extract_blocks_from_file(self, filepath: Path) -> list[Block]:
        # Skip sidecar metadata files themselves if they match the glob
        if filepath.name.endswith('.stmx') or filepath.name.endswith('.syntagmax'):
            return []

        lg.debug(f'Processing sidecar driver for original file: {filepath}')

        stmx_path = filepath.with_name(f'{filepath.name}.stmx')
        syntagmax_path = filepath.with_name(f'{filepath.name}.syntagmax')

        stmx_exists = stmx_path.exists()
        syntagmax_exists = syntagmax_path.exists()

        if stmx_exists and syntagmax_exists:
            msg = _("{driver} :: Both .stmx and .syntagmax sidecars are present for {file}").format(driver=self.driver(), file=filepath)
            return [ErrorBlock(message=msg, raw_text='')]

        if not stmx_exists and not syntagmax_exists:
            msg = _("{driver} :: Missing sidecar file for {file}").format(driver=self.driver(), file=filepath)
            return [ErrorBlock(message=msg, raw_text='')]

        sidecar_path = stmx_path if stmx_exists else syntagmax_path

        try:
            with open(sidecar_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            msg = _("{driver} :: Malformed YAML in sidecar {path}: {error}").format(driver=self.driver(), path=sidecar_path, error=str(e))
            return [ErrorBlock(message=msg, raw_text='')]
        except Exception as e:
            msg = _("{driver} :: Could not read sidecar {path}: {error}").format(driver=self.driver(), path=sidecar_path, error=str(e))
            return [ErrorBlock(message=msg, raw_text='')]

        if not isinstance(data, dict):
            msg = _("{driver} :: Sidecar {path} does not contain a valid YAML dictionary").format(driver=self.driver(), path=sidecar_path)
            return [ErrorBlock(message=msg, raw_text='')]

        if 'id' not in data:
            msg = _("{driver} :: Missing required 'id' field in sidecar {path}").format(driver=self.driver(), path=sidecar_path)
            return [ErrorBlock(message=msg, raw_text='')]

        aid = str(_pop_case_insensitive(data, 'id', UNDEFINED_ID))
        atype = str(_pop_case_insensitive(data, 'atype', self._record.default_atype))

        location = FileLocation(self._config.derive_path(filepath), self._config.derive_path(sidecar_path))

        builder = ArtifactBuilder(self._config, Artifact, self.driver(), location, self._metamodel, record=self._record)

        try:
            builder.add_id(aid, atype)
            builder.add_field('id', aid)

            for key, value in data.items():
                if isinstance(value, list):
                    for v in value:
                        builder.add_field(key, self._yaml_value_to_str(v, atype, key))
                else:
                    builder.add_field(key, self._yaml_value_to_str(value, atype, key))

            artifact = builder.build()
            raw_text = sidecar_path.read_text(encoding='utf-8')
            return [ArtifactBlock(artifact=artifact, raw_text=raw_text)]

        except ValidationError as e:
            msg = _("{driver} :: Validation error in {path}: {error}").format(driver=self.driver(), path=sidecar_path, error=str(e))
            return [ErrorBlock(message=msg, raw_text='')]
