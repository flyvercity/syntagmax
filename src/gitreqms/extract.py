# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from a given file using the appropriate extractor

import logging as lg
from pathlib import Path

from gitreqms.extractors.text import TextExtractor
from gitreqms.extractors.filename import FilenameExtractor
from gitreqms.extractors.obsidian import ObsidianExtractor
from gitreqms.extractors.markdown import MarkdownExtractor
from gitreqms.extractors.ipynb import IPynbExtractor
from gitreqms.artifact import Artifact, ARef
from gitreqms.config import Config
from gitreqms.utils import pprint
from gitreqms.errors import NonFatalError
from typing import Sequence
from gitreqms.config import Params

EXTRACTORS = {
    'text': TextExtractor,
    'filename': FilenameExtractor,
    'obsidian': ObsidianExtractor,
    'markdown': MarkdownExtractor,
    'ipynb': IPynbExtractor
}

def get_available_extractors() -> Sequence[str]:
    return list(EXTRACTORS.keys())

def print_artifact(artifact: Artifact):
    pprint(
        f'[magenta]{artifact.driver}[/magenta] :: '
        f'[cyan]{artifact.atype}[/cyan] :: '
        f'[green]{artifact.aid}[/green]'
        f' {artifact.metastring()}'
        f' (parents: {len(artifact.pids)})'
    )

def extract(config: Config) -> tuple[dict[ARef, Artifact], list[str]]:
    artifacts: Sequence[Artifact] = []
    errors: Sequence[str] = []

    for record in config.input_records():
        lg.debug(f'Processing record: {record["record_base"]} ({record["driver"]})')
        extractor = EXTRACTORS[record['driver']](config.params)
        record_artifacts, record_errors = extractor.extract(record)
        artifacts.extend(record_artifacts)
        errors.extend(record_errors)

    if config.params['verbose']:
        lg.debug('Listing raw artifacts:')

        for artifact in artifacts:
            print_artifact(artifact)

    artifact_map: dict[ARef, Artifact] = {}

    for a in artifacts:
        if a.ref() in artifact_map:
            errors.append(f'Duplicate artifact: {a} replaces {artifact_map[a.ref()]}')
        else:
            artifact_map[a.ref()] = a

    return artifact_map, errors
    
def extract_single(params: Params, driver: str, file: Path):
    lg.debug(f'Extracting from {file} ({driver})')
    extractor = EXTRACTORS[driver](params)
    artifacts, errors = extractor.extract_from_file(Path(file))

    for artifact in artifacts:
        print_artifact(artifact)

    if errors:
        raise NonFatalError(errors)
