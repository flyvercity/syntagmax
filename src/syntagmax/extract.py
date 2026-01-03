# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from a given file using the appropriate extractor

import logging as lg
from typing import Sequence

from syntagmax.extractors.text import TextExtractor
from syntagmax.extractors.filename import FilenameExtractor
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.extractors.ipynb import IPynbExtractor
from syntagmax.artifact import Artifact, ARef
from syntagmax.config import Config
from syntagmax.utils import pprint


EXTRACTORS = {
    'text': TextExtractor,
    'filename': FilenameExtractor,
    'obsidian': ObsidianExtractor,
    'ipynb': IPynbExtractor
}


def get_available_extractors() -> Sequence[str]:
    return list(EXTRACTORS.keys())


def print_artifact(artifact: Artifact):
    pprint(
        f'[magenta]{artifact.driver}[/magenta] :: '
        f'[cyan]{artifact.atype}[/cyan] :: '
        f'[green]{artifact.aid}[/green]'
        f' (parents: {len(artifact.pids)})'
    )


def extract(config: Config) -> tuple[dict[ARef, Artifact], list[str]]:
    artifacts: Sequence[Artifact] = []
    errors: Sequence[str] = []

    for record in config.input_records():
        lg.debug(f'Processing record: {record["record_base"]} ({record["driver"]})')
        extractor = EXTRACTORS[record['driver']](config, record)
        record_artifacts, record_errors = extractor.extract()
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
