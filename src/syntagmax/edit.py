# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-10
# Description: Renumbering artifacts.

import logging as lg
from collections import defaultdict

from syntagmax.artifact import UNDEFINED_ID
from syntagmax.config import Config
from syntagmax.extract import extract
from syntagmax.id_utils import _NUM_PATTERN, extract_number_from_id, count_num_macros


def _resolve_schema(aid: str, atype: str, config: Config) -> str:
    """Resolve the ID schema for an artifact.

    Precedence:
      1. If the artifact's current ID contains a schema macro ({num or {atype}),
         use the ID itself as the schema (it's a template).
      2. If the metamodel defines a schema for this artifact type, use it.
      3. Default: '{atype}-{num:3}'
    """
    if aid and ('{num' in aid or '{atype}' in aid):
        return aid

    if config.metamodel and atype in config.metamodel.get('artifacts', {}):
        attr_rules = config.metamodel['artifacts'][atype]['attributes'].get('id', [])
        if isinstance(attr_rules, dict):
            attr_rules = [attr_rules]
        for rule in attr_rules:
            if 'schema' in rule and rule['schema']:
                return rule['schema']

    return '{atype}-{num:3}'


def _is_template_id(aid: str) -> bool:
    """Check if an ID is a template (contains schema macros)."""
    return bool(aid and ('{num' in aid or '{atype}' in aid))


def _generate_id(schema: str, atype: str, number: int) -> str:
    """Generate a new ID from schema, atype, and number.

    Replaces {atype} with the artifact type name, and {num:N} / {num}
    with the zero-padded / plain number. Does not truncate if number
    exceeds the padding width.
    """
    new_id = schema.replace('{atype}', atype)

    def replacer(match):
        padding = match.group(1)
        if padding:
            return str(number).zfill(int(padding))
        return str(number)

    return _NUM_PATTERN.sub(replacer, new_id)


def renumber_artifacts(config: Config, atype: str | None = None, dry_run: bool = False, force: bool = False) -> bool:
    """Renumber artifact IDs using the two-pass max+1 algorithm.

    Returns True on success, False on validation failure or extraction errors.
    """
    errors = []
    artifacts_list = extract(config, errors)
    if errors:
        for error in errors:
            lg.error(error)
        return False

    # Filter artifacts if atype is given
    if atype:
        target_artifacts = [a for a in artifacts_list if a.atype == atype]
    else:
        target_artifacts = artifacts_list

    # Sort artifacts by their current location to have a stable renumbering
    target_artifacts.sort(key=lambda a: str(a.location))

    # Pre-validation: check that no resolved template schema has multiple {num} macros
    for artifact in target_artifacts:
        schema = _resolve_schema(artifact.aid, artifact.atype, config)
        if count_num_macros(schema) > 1:
            lg.error(f"Schema '{schema}' for artifact type '{artifact.atype}' has multiple {{num}} macros (only one allowed). Aborting.")
            return False

    # === Pass 1: Identify valid IDs and compute max number per type ===
    max_number: dict[str, int] = defaultdict(int)
    seen_ids: dict[str, list] = defaultdict(list)  # aid -> list of artifacts

    for artifact in target_artifacts:
        schema = _resolve_schema(artifact.aid, artifact.atype, config)

        # Skip if schema has no {num} — we can't extract or assign numbers
        if count_num_macros(schema) == 0:
            continue

        # Skip template IDs and undefined IDs — they are not valid
        if _is_template_id(artifact.aid):
            continue
        if artifact.aid == UNDEFINED_ID or not artifact.aid:
            continue

        # Try to match the artifact ID against the schema
        number = extract_number_from_id(artifact.aid, schema, artifact.atype)
        if number is not None:
            # Valid ID
            max_number[artifact.atype] = max(max_number[artifact.atype], number)
            seen_ids[artifact.aid].append(artifact)

    # Detect duplicates
    duplicates = {aid: arts for aid, arts in seen_ids.items() if len(arts) > 1}

    # === Pass 2: Assign new IDs ===
    counters: dict[str, int] = {}
    if force:
        # Force mode: start from 1 for all types
        for artifact in target_artifacts:
            counters.setdefault(artifact.atype, 1)
    else:
        # Normal mode: start from max+1
        for artifact in target_artifacts:
            if artifact.atype not in counters:
                counters[artifact.atype] = max_number.get(artifact.atype, 0) + 1

    updates_by_file = defaultdict(list)
    kept = 0
    changed = 0
    total = 0

    for artifact in target_artifacts:
        schema = _resolve_schema(artifact.aid, artifact.atype, config)

        # Skip if schema has no {num} — can't assign numbers
        if count_num_macros(schema) == 0:
            total += 1
            kept += 1
            continue

        total += 1

        needs_renumber = False
        if force:
            # Force mode: renumber everything
            needs_renumber = True
        else:
            # Normal mode: renumber undefined, empty, template IDs,
            # or IDs that don't match the schema
            if artifact.aid == UNDEFINED_ID or not artifact.aid:
                needs_renumber = True
            elif _is_template_id(artifact.aid):
                needs_renumber = True
            else:
                # Check if the ID matches the schema — if not, it needs renumbering
                number = extract_number_from_id(artifact.aid, schema, artifact.atype)
                if number is None:
                    needs_renumber = True

        if needs_renumber:
            current_atype = artifact.atype
            number = counters[current_atype]
            counters[current_atype] = number + 1

            new_id = _generate_id(schema, current_atype, number)
            old_id_display = artifact.aid if artifact.aid != UNDEFINED_ID else '<undefined>'

            if dry_run:
                lg.info(f'DRY-RUN: Would renumber {old_id_display} to {new_id} at {artifact.location}')
            else:
                lg.info(f'Renumbering {old_id_display} to {new_id} at {artifact.location}')
                updates_by_file[artifact.location.loc_file].append((artifact, new_id))

            changed += 1
        else:
            kept += 1

    lg.info(f'Preserved {kept} valid IDs. Renumbered {changed} artifacts. Total: {total}.')

    if duplicates:
        dup_list = ', '.join(sorted(duplicates.keys()))
        lg.warning(f'Duplicate valid IDs found: {dup_list}')

    if not dry_run:
        from syntagmax.extract import EXTRACTORS

        # Perform updates grouped by file
        for loc_file, updates in updates_by_file.items():
            # All artifacts in the same file should belong to the same record
            record = updates[0][0].record
            if record:
                driver = record.driver
                extractor = EXTRACTORS[driver](config, record, config.metamodel)
                if hasattr(extractor, 'update_artifacts'):
                    # Efficient bulk update
                    extractor.update_artifacts(loc_file, updates)
                else:
                    lg.warning(f'Driver {driver} does not support renumbering yet')
            else:
                lg.error(f'Could not find input record for artifacts at {loc_file}')

    return True
