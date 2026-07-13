# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-04
# Description: Bulk attribute manipulation for artifacts (edit attrs command).

import csv
import logging as lg
from pathlib import Path
from collections import defaultdict

from syntagmax.artifact import Artifact
from syntagmax.config import Config
from syntagmax.errors import FatalError
from syntagmax.extract import EXTRACTORS, extract
from syntagmax.utils import pprint


def load_csv_mapping(csv_path: Path, id_column: str, value_column: str, delimiter: str = ',') -> dict[str, str]:
    """Load a CSV file and build an ID-to-value mapping.

    Args:
        csv_path: Path to the CSV file.
        id_column: Column name used to match artifact IDs.
        value_column: Column name used as the attribute value.
        delimiter: CSV column delimiter.

    Returns:
        Dict mapping artifact IDs to attribute values.

    Raises:
        FatalError: If the file is malformed or columns are missing.
    """
    if not csv_path.exists():
        raise FatalError(f'CSV file not found: {csv_path}')

    mapping: dict[str, str] = {}

    try:
        # Handle UTF-8 BOM
        content = csv_path.read_text(encoding='utf-8-sig')
        reader = csv.DictReader(content.splitlines(), delimiter=delimiter)

        if reader.fieldnames is None:
            raise FatalError(f'CSV file is empty or has no header: {csv_path}')

        if id_column not in reader.fieldnames:
            raise FatalError(f'CSV column "{id_column}" not found in {csv_path}. Available columns: {", ".join(reader.fieldnames)}')

        if value_column not in reader.fieldnames:
            raise FatalError(f'CSV column "{value_column}" not found in {csv_path}. Available columns: {", ".join(reader.fieldnames)}')

        for row in reader:
            aid = row.get(id_column, '').strip()
            value = row.get(value_column, '').strip()
            if not aid:
                continue
            if aid in mapping:
                lg.warning(f'Duplicate ID "{aid}" in CSV; using last value')
            mapping[aid] = value

    except UnicodeDecodeError as e:
        raise FatalError(f'Failed to read CSV file (encoding error): {e}')
    except csv.Error as e:
        raise FatalError(f'Failed to parse CSV file: {e}')

    return mapping


def _get_mandatory_attributes(metamodel: dict, atype: str) -> list[str]:
    """Get mandatory attribute names from the metamodel for a given artifact type.

    Excludes 'id' and 'contents' which are always handled separately.
    """
    artifacts = metamodel.get('artifacts', {})
    artifact_def = artifacts.get(atype)
    if not artifact_def:
        return []

    attributes = artifact_def.get('attributes', {})
    mandatory_attrs = []

    for attr_name, rules in attributes.items():
        if attr_name.lower() in ('id', 'contents'):
            continue
        if isinstance(rules, dict):
            rules = [rules]
        for rule in rules:
            if rule.get('presence') == 'mandatory' and rule.get('condition') is None:
                mandatory_attrs.append(attr_name)
                break

    return mandatory_attrs


def manipulate_attributes(
    config: Config,
    section: str,
    operation: str,
    target_type: str,
    name: str | None,
    value: str | None,
    csv_mapping: dict[str, str] | None,
    dry_run: bool,
) -> None:
    """Orchestrate bulk attribute manipulation across artifacts in a section.

    Args:
        config: Loaded project configuration.
        section: Input record name to target.
        operation: 'add', 'del', or 'replace'.
        target_type: 'attr' (YAML) or 'field' (inline markers).
        name: Attribute name (None for metamodel-driven add).
        value: Attribute value (None defaults to 'TBD' for add).
        csv_mapping: Optional ID-to-value mapping from CSV.
        dry_run: If True, print planned changes without modifying files.
    """
    # --- Validation pass ---

    # Find the target input record
    target_record = None
    for record in config.input_records():
        if record.name == section:
            target_record = record
            break

    if target_record is None:
        raise FatalError(f'Input section "{section}" not found in configuration')

    if target_record.driver != 'obsidian':
        raise FatalError(f'Section "{section}" uses driver "{target_record.driver}". Only the "obsidian" driver is supported for attribute manipulation.')

    # Resolve attribute names to manipulate
    attr_names: list[str]
    if name is None:
        # Metamodel-driven add: add all mandatory attributes
        if config.metamodel is None:
            raise FatalError('Cannot add mandatory attributes without a metamodel. Either specify --name or configure a metamodel in your project.')
        attr_names = _get_mandatory_attributes(config.metamodel, target_record.default_atype)
        if not attr_names:
            pprint(f'[yellow]No mandatory attributes found in metamodel for type "{target_record.default_atype}"[/yellow]')
            return
        # For metamodel-driven add, always use TBD
        value = 'TBD'
    else:
        attr_names = [name]

    # For 'add' without explicit value, default to TBD
    if operation == 'add' and value is None and csv_mapping is None:
        value = 'TBD'

    # Metamodel validation: warn if attribute not defined
    if config.metamodel and name is not None:
        artifacts_meta = config.metamodel.get('artifacts', {})
        atype_meta = artifacts_meta.get(target_record.default_atype, {})
        known_attrs = atype_meta.get('attributes', {})
        if name.lower() not in {k.lower() for k in known_attrs}:
            lg.warning(f'Attribute "{name}" is not defined in the metamodel for type "{target_record.default_atype}". It will still be added.')

    # --- Extract artifacts ---
    errors: list[str] = []
    all_artifacts = extract(config, errors)
    if errors:
        for e in errors:
            lg.error(e)

    # Filter to target section
    section_artifacts = [a for a in all_artifacts if a.record and a.record.name == section]

    if not section_artifacts:
        pprint(f'[yellow]No artifacts found in section "{section}"[/yellow]')
        return

    # --- Computation pass ---
    extractor = EXTRACTORS[target_record.driver](config, target_record, config.metamodel)

    # Group artifacts by file
    by_file: dict[str, list[Artifact]] = defaultdict(list)
    for artifact in section_artifacts:
        if artifact.location:
            by_file[artifact.location.filepath()].append(artifact)

    modified_count = 0
    skipped_count = 0
    unmatched_count = 0
    file_writes: list[tuple[Path, str]] = []

    for loc_file, file_artifacts in by_file.items():
        updates: list[tuple[Artifact, dict[str, str | None], str]] = []

        for artifact in file_artifacts:
            attrs_delta: dict[str, str | None] = {}
            for attr_name in attr_names:
                # Resolve value for this artifact
                resolved_value = _resolve_value(artifact, attr_name, operation, value, csv_mapping)

                if resolved_value is _SKIP:
                    unmatched_count += 1
                    continue

                # Check if we should skip (add with existing attr)
                if operation == 'add' and _artifact_has_attr(artifact, attr_name, target_type):
                    if dry_run:
                        pprint(f"[dim]DRY-RUN: {artifact.aid} already has {target_type} '{attr_name}', skipping (operation: add)[/dim]")
                    skipped_count += 1
                    continue

                if dry_run:
                    op_desc = {'add': 'add', 'del': 'remove', 'replace': 'replace'}[operation]
                    val_desc = f" = '{resolved_value}'" if resolved_value is not None else ''
                    pprint(f"[green]DRY-RUN: Would {op_desc} {target_type} '{attr_name}'{val_desc} on {artifact.aid} at {loc_file}[/green]")

                attrs_delta[attr_name] = resolved_value

            if attrs_delta:
                updates.append((artifact, attrs_delta, operation))
                modified_count += 1

        if updates and not dry_run:
            new_content = extractor.update_artifact_attributes(loc_file, updates, target_type)
            filepath = config.base_dir() / loc_file
            file_writes.append((filepath, new_content))

    # --- Write pass ---
    if not dry_run:
        write_errors: list[str] = []
        for filepath, content in file_writes:
            try:
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    f.write(content)
            except OSError as e:
                msg = f'Failed to write "{filepath}": {e}'
                write_errors.append(msg)
                lg.error(msg)

        if write_errors:
            raise FatalError('One or more files could not be written; see logs for details')
    # --- Summary ---
    if dry_run:
        summary = f'\n[bold]Summary: {modified_count} artifacts would be modified, {skipped_count} skipped'
    else:
        summary = f'\n[bold]Summary: {modified_count} artifacts modified, {skipped_count} skipped'

    if csv_mapping is not None and unmatched_count > 0:
        summary += f', {unmatched_count} unmatched in CSV'
    summary += '[/bold]'
    pprint(summary)


class _SkipSentinel:
    """Sentinel value indicating an artifact should be skipped."""

    pass


_SKIP = _SkipSentinel()


def _resolve_value(
    artifact: Artifact,
    attr_name: str,
    operation: str,
    literal_value: str | None,
    csv_mapping: dict[str, str] | None,
) -> str | None | _SkipSentinel:
    """Resolve the value for an attribute manipulation.

    Returns _SKIP if the artifact should be skipped (CSV miss with no fallback).
    Returns None for deletion operations.
    """
    if operation == 'del':
        return None

    if csv_mapping is not None:
        csv_value = csv_mapping.get(artifact.aid)
        if csv_value is not None:
            return csv_value
        # CSV miss: fall back to literal value if provided
        if literal_value is not None:
            return literal_value
        # No fallback available
        lg.warning(f'Artifact "{artifact.aid}" at {artifact.location} not found in CSV mapping')
        return _SKIP

    return literal_value


def _artifact_has_attr(artifact: Artifact, attr_name: str, target_type: str) -> bool:
    """Check if an artifact already has the specified attribute."""
    from syntagmax.extractors.markdown import MarkdownArtifact

    if target_type == 'attr':
        # Check YAML attrs via yaml_data if available
        if isinstance(artifact, MarkdownArtifact) and artifact.yaml_data is not None:
            attrs = artifact.yaml_data.get('attrs', {})
            if attrs and any(k.lower() == attr_name.lower() for k in attrs):
                return True
            return False
        # Fall back to checking fields dict
        return any(k.lower() == attr_name.lower() for k in artifact.fields if k.lower() not in ('id', 'contents'))
    else:
        # For inline fields, check source_metadata if available
        if isinstance(artifact, MarkdownArtifact) and artifact.source_metadata:
            return attr_name.lower() in artifact.source_metadata and artifact.source_metadata[attr_name.lower()] == 'markdown'
        # Fall back to checking fields dict
        return any(k.lower() == attr_name.lower() for k in artifact.fields if k.lower() not in ('id', 'contents'))
