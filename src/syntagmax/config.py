# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Configuration for the Syntagmax RMS.

import os
from pathlib import Path
import tomllib
import logging as lg
import json
from dataclasses import dataclass

from benedict import benedict
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


class AIConfig(BaseModel):
    provider: str = Field(default='ollama', description='AI provider (ollama, anthropic, openai, gemini, bedrock)')
    model: str | None = Field(default=None, description='Model name to use')
    # Provider-specific configurations
    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)
    aws_access_key_id: str | None = Field(default=None)
    aws_secret_access_key: str | None = Field(default=None)
    aws_region_name: str | None = Field(default=None)
    ollama_host: str = Field(default='http://localhost:11434')
    timeout_s: float = Field(default=60.0)


class ConfigFile(BaseModel):
    base: str = Field(..., description='Base directory path')
    input: list[InputConfig] = Field(..., description='Input configuration records')
    metrics: MetricsConfig = Field(MetricsConfig(), description='Metrics configuration')
    ai: AIConfig = Field(default_factory=AIConfig, description='AI configuration')


class Config:
    params: Params
    metrics: MetricsConfig
    ai: AIConfig
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
            config_data = benedict()

            # Global config
            global_config_path = Path(os.path.expanduser('~/.syntagmax/config'))
            if global_config_path.exists():
                lg.info(f'Loading global configuration from {global_config_path}')
                try:
                    global_data = tomllib.loads(global_config_path.read_text(encoding='utf-8'))
                    config_data.merge(global_data)
                except Exception as e:
                    lg.warning(f'Failed to load global config: {e}')

            # Project config
            project_data = tomllib.loads(config_file.read_text(encoding='utf-8'))
            config_data.merge(project_data)

            if self.params['verbose']:
                json_config = json.dumps(config_data, indent=4)
                lg.debug(f'Configuration file content: {json_config}')

            config_model = ConfigFile.model_validate(config_data)

            lg.debug(f'Root directory: {root_dir}. Base directory: {config_model.base}')

            self._base_dir = Path(root_dir, config_model.base).resolve()
            lg.debug(f'Base directory: {self._base_dir}')
            self._read_input_records(config_model.input)

            self.metrics = config_model.metrics
            self.ai = config_model.ai

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
