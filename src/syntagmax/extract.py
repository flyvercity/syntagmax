# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from a given file using the appropriate extractor

import logging as lg
from typing import Sequence

from syntagmax.extractors.text import TextExtractor
from syntagmax.extractors.sidecar import SidecarExtractor
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.extractors.ipynb import IPynbExtractor
from syntagmax.artifact import Artifact
from syntagmax.config import Config
from syntagmax.utils import pprint


EXTRACTORS = {
    'text': TextExtractor,
    'sidecar': SidecarExtractor,
    'obsidian': ObsidianExtractor,
    'ipynb': IPynbExtractor,
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


def extract(config: Config) -> tuple[list[Artifact], list[str]]:
    artifacts: list[Artifact] = []
    errors: list[str] = []

    for record in config.input_records():
        lg.debug(f'Processing record: {record.name} ({record.driver})')
        extractor = EXTRACTORS[record.driver](config, record, config.metamodel)
        record_artifacts, record_errors = extractor.extract()
        artifacts.extend(record_artifacts)
        errors.extend(record_errors)

    if config.params['verbose']:
        lg.debug('Listing raw artifacts:')

        for artifact in artifacts:
            print_artifact(artifact)

    return artifacts, errors


def build_artifact_map(artifacts_list: list[Artifact]) -> tuple[dict[str, Artifact], list[str]]:
    artifacts: dict[str, Artifact] = {}
    errors: list[str] = []

    for a in artifacts_list:
        print('<<' + a.aid + '>>')
        if not a.aid:
            errors.append(f'Artifact {a.atype} at {a.location} has no ID')
            continue
        if a.aid in artifacts:
            errors.append(
                f'Duplicate artifact ID: {a.aid} at {a.location} (already defined at {artifacts[a.aid].location})'
            )
            continue
        artifacts[a.aid] = a

    return artifacts, errors
