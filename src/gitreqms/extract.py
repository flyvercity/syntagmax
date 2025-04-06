# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06

import logging as lg
from pathlib import Path

from gitreqms.extractors.text import TextExtractor
from gitreqms.extractors.filename import FilenameExtractor
from gitreqms.extractors.obsidian import ObsidianExtractor
from gitreqms.artifact import Artifact
from gitreqms.config import Params, Config
from gitreqms.utils import pprint
from gitreqms.errors import NonFatalError
from typing import Sequence

EXTRACTORS = {
    'text': TextExtractor,
    'filename': FilenameExtractor,
    'obsidian': ObsidianExtractor
}

def get_available_extractors() -> Sequence[str]:
    return list(EXTRACTORS.keys())

def print_artifacts(artifacts: Sequence[Artifact]):
    for artifact in artifacts:
        pprint(
            f'[magenta]{artifact.driver()}[/magenta] :: '
            f'[cyan]{artifact.atype}[/cyan] :: '
            f'[green]{artifact.aid}[/green]'
            f' {artifact.metastring()}'
        )

def extract(params: Params, config: Config) -> tuple[Sequence[Artifact], list[str]]:
    artifacts: Sequence[Artifact] = []
    errors: Sequence[str] = []

    for record in config.input_records():
        lg.debug(f'Processing record: {record["record_base"]} ({record["driver"]})')
        extractor = EXTRACTORS[record['driver']](params)
        record_artifacts, record_errors = extractor.extract(record)
        artifacts.extend(record_artifacts)
        errors.extend(record_errors)

    if params['verbose']:
        lg.debug('Listing raw artifacts:')
        print_artifacts(artifacts)

    return artifacts, errors
    
def extract_single(obj: Params, driver: str, file: Path):
    extractor = EXTRACTORS[driver](obj)
    artifacts, errors = extractor.extract_from_file(Path(file))

    print_artifacts(artifacts)

    if errors:
        raise NonFatalError(errors)
