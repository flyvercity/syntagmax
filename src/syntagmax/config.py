# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Configuration for the RMS.

from pathlib import Path
import tomllib
import logging as lg
from typing import TypedDict, Any
import json

import click

from syntagmax.params import Params
from syntagmax.model import IModel, build_model

class InputRecord(TypedDict):
    record_base: Path
    record_subdir: Path
    filepaths: list[Path]
    driver: str


DEFAULT_FILTERS = {
    'obsidian': '**/*.md',
    'ipynb': '**/*.ipynb',
    'markdown': '**/*.md'
} 

class Config:
    def __init__(self, params: Params, config_filename: Path):
        self.params = params
        self._input_records: list[InputRecord] = []
        self._read_config(config_filename)
        self.model: IModel = build_model(self.params)

    def _read_config(self, config_filename: Path):
        try:
            config_file = Path(config_filename).resolve()
            lg.info(f'Using configuration file: {config_file}')

            root_dir = config_file.parent
            config = tomllib.loads(config_file.read_text(encoding='utf-8'))

            if self.params['verbose']:
                lg.debug(f'Configuration file content: {config}')
                click.echo(json.dumps(config, indent=4))

            base = config.get('base')

            if not base:
                raise UserWarning('Missing `base` parameter')

            self._base_dir = Path(root_dir, base).resolve()
            lg.debug(f'Base directory: {self._base_dir}')
            self._read_input_records(config)

        except Exception as exc:
            lg.error(f'Error during configuration: {exc}')
            raise UserWarning('Bad configuration file')
            
    def _read_input_records(self, config: dict[str, Any]):
        input = config.get('input')

        if not input:
            raise UserWarning('Missing input section')

        for input_record in input:
            path = input_record.get('path')
            record_base = Path(self._base_dir, path)

            if not path:
                raise UserWarning('Missing `input.path` parameter')

            subdir = input_record.get('subdir')

            if subdir:
                record_subdir = Path(record_base, subdir)
            else:
                record_subdir = record_base

            driver = input_record.get('driver')

            if not driver:
                raise UserWarning('Missing `input.driver` parameter')

            filter = input_record.get('filter')
            glob = filter or '**/*'

            if not filter and driver in DEFAULT_FILTERS:
                lg.info(f'Using default filter ({DEFAULT_FILTERS[driver]}) for {path}')
                glob = DEFAULT_FILTERS[driver]

            lg.debug(f'Adding input files from {record_subdir} with filter {glob}')
            filepaths = Path(record_subdir, Path(record_subdir)).glob(glob)

            self._input_records.append(
                InputRecord(
                    record_base=record_base,
                    record_subdir=record_subdir,
                    filepaths=list(filepaths),
                    driver=driver
                )
            )

        for input_record in self._input_records:
            lg.info(f'Input record: {input_record["record_subdir"]}')
            lg.debug(f'Input files: {len(input_record["filepaths"])}')

    def base_dir(self):
        return self._base_dir

    def input_records(self) -> list[InputRecord]:
        return self._input_records
