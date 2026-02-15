# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Configuration for the Syntagmax RMS.

from pathlib import Path
import tomllib
import logging as lg
import json
from dataclasses import dataclass

from pydantic import BaseModel, Field

from syntagmax.params import Params
from syntagmax.model import IModel, build_model


@dataclass
class InputRecord:
    name: str
    record_base: Path
    filepaths: list[Path]
    driver: str
    default_atype: str


DEFAULT_FILTERS = {
    'obsidian': '**/*.md',
    'ipynb': '**/*.ipynb',
    'markdown': '**/*.md'
}


class InputConfig(BaseModel):
    name: str = Field(..., description='Input source name')
    dir: str = Field(..., description='Subdirectory relative to base directory')
    driver: str = Field(..., description='Driver type for processing')
    filter: str | None = Field(default=None, description='File filter pattern')
    atype: str = Field('REQ', description='Default artifact type')


class MetricsConfig(BaseModel):
    enabled: bool = Field(default=False, description='Enable metrics collection')
    requirement_type: str = Field(default='REQ', description='Requirement type')
    status_field: str = Field(default='status', description='Status attribute name')
    verify_field: str = Field(default='verify', description='Verify attribute name')
    tbd_marker: str = Field(default='TBD', description='TBD detection marker')
    output_format: str = Field(default='rich', description='Output format', pattern='^(rich|markdown)$')
    output_file: str = Field(default='console', description='Output file name')
    template: str | None = Field(default=None, description='Path to custom Jinja template')
    locale: str = Field(default='en', description='Locale code for localization')


class ConfigFile(BaseModel):
    base: str = Field(..., description='Base directory path')
    input: list[InputConfig] = Field(..., description='Input configuration records')
    metrics: MetricsConfig = Field(MetricsConfig(), description='Metrics configuration')


class Config:
    params: Params
    metrics: MetricsConfig
    model: IModel

    def __init__(self, params: Params, config_filename: Path):
        self.params = params
        self._input_records: list[InputRecord] = []
        self._read_config(config_filename)
        self.model = build_model(self.params)

    def _read_config(self, config_filename: Path):
        try:
            config_file = Path(config_filename).resolve()
            lg.info(f'Using configuration file: {config_file}')

            root_dir = config_file.parent
            config_data = tomllib.loads(config_file.read_text(encoding='utf-8'))

            if self.params['verbose']:
                json_config = json.dumps(config_data, indent=4)
                lg.debug(f'Configuration file content: {json_config}')

            config_model = ConfigFile.model_validate(config_data)

            lg.debug(f'Root directory: {root_dir}. Base directory: {config_model.base}')

            self._base_dir = Path(root_dir, config_model.base).resolve()
            lg.debug(f'Base directory: {self._base_dir}')
            self._read_input_records(config_model.input)

            self.metrics = config_model.metrics

            if not config_model.metrics.enabled:
                lg.warning('Metrics collection is disabled')

        except Exception as exc:
            lg.error(f'Error during configuration: {exc}')
            raise UserWarning('Bad configuration file')

    def _read_input_records(self, input_configs: list[InputConfig]):
        for input_config in input_configs:
            name = input_config.name
            record_base = Path(self._base_dir, input_config.dir)
            glob = input_config.filter or '**/*'

            if not input_config.filter and input_config.driver in DEFAULT_FILTERS:
                lg.info(
                    f'Using default filter ({DEFAULT_FILTERS[input_config.driver]}) for {record_base}'
                )
                glob = DEFAULT_FILTERS[input_config.driver]

            lg.debug(f'Adding input files from {name} with filter {glob}')
            filepaths = Path(record_base).glob(glob)

            self._input_records.append(
                InputRecord(
                    name=name,
                    record_base=record_base,
                    filepaths=list(filepaths),
                    driver=input_config.driver,
                    default_atype=input_config.atype
                )
            )

        for input_record in self._input_records:
            lg.info(f'Input record: {input_record.name}')
            lg.debug(f'Input files: {len(input_record.filepaths)}')

    def base_dir(self):
        return self._base_dir

    def derive_path(self, path: Path) -> str:
        rel_path = path.absolute().relative_to(self._base_dir.absolute())
        return rel_path.as_posix()

    def input_records(self) -> list[InputRecord]:
        return self._input_records
