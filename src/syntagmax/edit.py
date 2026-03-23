# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-10
# Description: Renumbering artifacts.

import logging as lg
import re
from collections import defaultdict

from syntagmax.artifact import UNDEFINED_ID
from syntagmax.config import Config
from syntagmax.extract import extract

def renumber_artifacts(
    config: Config,
    atype: str | None = None,
    schema_override: str | None = None,
    dry_run: bool = False
):
    artifacts_list, errors = extract(config)
    if errors:
        for error in errors:
            lg.error(error)
        return

    # Filter artifacts if atype is given
    if atype:
        target_artifacts = [a for a in artifacts_list if a.atype == atype]
    else:
        target_artifacts = artifacts_list

    # Sort artifacts by their current location to have a stable renumbering
    target_artifacts.sort(key=lambda a: str(a.location))

    # Project-unique sequential number
    project_num = 1

    # Group by file for efficiency
    updates_by_file = defaultdict(list)

    num_pattern = re.compile(r'\{num(?::(\d+))?\}')

    for artifact in target_artifacts:
        current_atype = artifact.atype

        # Determine schema using precedence:
        # 1. Existing ID contains a schema macro
        # 2. schema_override (--schema)
        # 3. Metamodel schema
        # 4. Default {atype}-{num:3}

        # To check if existing ID contains a schema macro, we need to know the RAW ID
        # from the source. Artifact.aid currently holds the parsed ID.
        # If the ID was something like {num}, it might have been parsed as literally "{num}".

        schema = None
        if artifact.aid and ('{num' in artifact.aid or '{atype}' in artifact.aid):
            schema = artifact.aid
        elif schema_override:
            schema = schema_override
        elif config.metamodel and current_atype in config.metamodel.get('artifacts', {}):
            schema = config.metamodel['artifacts'][current_atype]['attributes'].get('id', {}).get('schema')

        if not schema:
            schema = "{atype}-{num:3}"

        # Substitute macro
        new_id = schema.replace("{atype}", current_atype)

        def replacer(match):
            padding = match.group(1)
            if padding:
                return str(project_num).zfill(int(padding))
            return str(project_num)

        new_id = num_pattern.sub(replacer, new_id)

        # Log what we are doing
        old_id_display = artifact.aid if artifact.aid != UNDEFINED_ID else "<undefined>"

        if new_id != artifact.aid:
            if dry_run:
                lg.info(f"DRY-RUN: Would renumber {old_id_display} to {new_id} at {artifact.location}")
            else:
                lg.info(f"Renumbering {old_id_display} to {new_id} at {artifact.location}")
                updates_by_file[artifact.location.loc_file].append((artifact, new_id))

        project_num += 1

    if not dry_run:
        from syntagmax.extract import EXTRACTORS
        # Perform updates grouped by file
        for loc_file, updates in updates_by_file.items():
            # All artifacts in the same file should have the same driver
            driver = updates[0][0].driver
            record = next((r for r in config.input_records() if r.driver == driver), None)
            if record:
                extractor = EXTRACTORS[driver](config, record, config.metamodel)
                if hasattr(extractor, 'update_artifacts'):
                    # Efficient bulk update
                    extractor.update_artifacts(loc_file, updates)
                else:
                    lg.warning(f"Driver {driver} does not support renumbering yet")
            else:
                lg.error(f"Could not find input record for driver {driver}")
