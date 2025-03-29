from pathlib import Path
import tomllib
import logging as lg


class InputRecord:
    def __init__(self, record_base, filepaths, driver):
        self._record_base = record_base
        self._filepaths = filepaths
        self._driver = driver


class Config:
    def __init__(self, params):
        self._input_records = []

        try:
            config_file = Path(params['config']).resolve()
            lg.debug(f'Using configuration file: {config_file}')
            root_dir = config_file.parent
            config = tomllib.loads(config_file.read_text())

            if params.get('verbose'):
                lg.debug(f'Configuration file content: {config}')

            if config.get('version') != 1:
                raise UserWarning('Unknown configuration file version (expected 1)')

            base = config.get('base')

            if not base:
                raise UserWarning('Missing base_dir parameter')

            self._base_dir = Path(root_dir, base).resolve()
            lg.debug(f'Base directory: {self._base_dir}')

            input = config.get('input')

            if not input:
                raise UserWarning('Missing input section')

            for input_record in input:
                path = input_record.get('path')
                record_base = Path(self._base_dir, path)

                if not path:
                    raise UserWarning('Missing input.path parameter')

                driver = input_record.get('driver')

                if not driver:
                    raise UserWarning('Missing input.driver parameter')

                filter = input_record.get('filter')
                glob = filter or '**/*'

                if not filter and driver == 'obsidian':
                    lg.info(f'Using default filter (**/*.md) for {path}')
                    glob = '**/*.md'

                lg.debug(f'Adding input files from {path} with filter {glob}')
                filepaths = Path(base, Path(path)).glob(glob)

                self._input_records.append(
                    InputRecord(record_base, filepaths, driver)
                )

        except Exception as exc:
            lg.error(f'Error during configuration: {exc}')
            raise UserWarning('Bad configuration file')

        for input_record in self._input_records:
            lg.info(f'Input record: {input_record._record_base}')
            lg.debug(f'Input files: {len(list(input_record._filepaths))}')

    def base_dir(self):
        return self._base_dir

    def input_records(self):
        return self._input_records