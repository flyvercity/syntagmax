from pathlib import Path
import tomllib
import logging as lg
from typing import TypedDict
import json

import click

from gitreqms.model import IModel

class Params(TypedDict):
    verbose: bool
    model: IModel

class InputRecord(TypedDict):
    record_base: Path
    record_subdir: Path
    filepaths: list[Path]
    driver: str

class Config:
    def __init__(self, params: Params, config_filename: Path):
        self._input_records: list[InputRecord] = []

        try:
            config_file = Path(config_filename).resolve()
            lg.info(f'Using configuration file: {config_file}')

            root_dir = config_file.parent
            config = tomllib.loads(config_file.read_text())

            if params['verbose']:
                lg.debug(f'Configuration file content: {config}')
                click.echo(json.dumps(config, indent=4))

            base = config.get('base')

            if not base:
                raise UserWarning('Missing `base` parameter')

            self._base_dir = Path(root_dir, base).resolve()
            lg.debug(f'Base directory: {self._base_dir}')

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

                if not filter and driver == 'obsidian':
                    lg.info(f'Using default filter (**/*.md) for {path}')
                    glob = '**/*.md'

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

        except Exception as exc:
            lg.error(f'Error during configuration: {exc}')
            raise UserWarning('Bad configuration file')

        for input_record in self._input_records:
            lg.info(f'Input record: {input_record["record_subdir"]}')
            lg.debug(f'Input files: {len(input_record["filepaths"])}')

    def base_dir(self):
        return self._base_dir

    def input_records(self) -> list[InputRecord]:
        return self._input_records
