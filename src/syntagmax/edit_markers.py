# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-11
# Description: Renumbering marker IDs on non-artifact marked text blocks.

import logging as lg
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from syntagmax.blocks import TextBlock
from syntagmax.config import Config
from syntagmax.extract import EXTRACTORS
from syntagmax.utils import pprint


@dataclass
class MarkerReplacement:
    """A single replacement to apply to a source file."""
    offset: int
    old_tag_len: int
    new_tag: str
    marker: str
    new_id: int


def _parse_numeric_id(id_str: str) -> int | None:
    """Parse an existing block ID as a non-negative integer.

    Returns the integer value, or None if the string is not a valid
    non-negative integer.
    """
    try:
        value = int(id_str)
        if value >= 0:
            return value
    except (ValueError, TypeError):
        pass
    return None


def _compute_tag_replacement(content: str, offset: int, marker_name_upper: str, new_id: int) -> MarkerReplacement | None:
    """Compute the replacement for an opening tag at the given offset.

    Reads the original marker name casing from the file content and determines
    the tag length. Returns None if the tag cannot be found at the offset.
    """
    # The content at offset should be '[MARKER]' (case-insensitive, no ID)
    if offset >= len(content) or content[offset] != '[':
        return None

    # Extract original marker name (preserving case)
    start = offset + 1
    end = start
    while end < len(content) and content[end] not in (']', ' ', '\t'):
        end += 1

    original_name = content[start:end]
    if original_name.upper() != marker_name_upper:
        return None

    # Verify the tag closes immediately after the name
    if end >= len(content) or content[end] != ']':
        return None

    old_tag_len = end - offset + 1  # includes both brackets
    new_tag = f'[{original_name} {new_id}]'

    return MarkerReplacement(
        offset=offset,
        old_tag_len=old_tag_len,
        new_tag=new_tag,
        marker=marker_name_upper,
        new_id=new_id,
    )


@dataclass
class _UnmarkedBlock:
    """An unmarked block that needs an ID assigned."""
    filepath: Path
    block: TextBlock


def renumber_markers(
    config: Config,
    section: str | None = None,
    marker_filter: str | None = None,
    dry_run: bool = False,
) -> None:
    """Renumber unmarked fragment blocks with sequential numeric IDs.

    Args:
        config: Loaded project configuration.
        section: Optional input record name to restrict to.
        marker_filter: Optional marker type filter (e.g., 'COM').
        dry_run: If True, print planned changes without modifying files.
    """
    # Select target records
    target_records = []
    for record in config.input_records():
        if not record.markers:
            continue
        if record.driver != 'obsidian':
            continue
        if section and record.name != section:
            continue
        target_records.append(record)

    if section and not target_records:
        pprint(f'[red]Error: Section "{section}" not found or has no markers configured.[/red]')
        return

    if not target_records:
        pprint('[yellow]No input records with markers found.[/yellow]')
        return

    # Normalize marker filter
    if marker_filter:
        marker_filter = marker_filter.upper()
        # Validate that at least one record configures this marker
        any_has_marker = any(marker_filter in r.markers for r in target_records)
        if not any_has_marker:
            pprint(f'[yellow]Warning: No input record configures marker "{marker_filter}".[/yellow]')
            return

    # Phase 1: Extract all blocks and collect existing numeric IDs per marker type
    # Also collect unmarked blocks that need IDs
    existing_ids: dict[str, list[int]] = defaultdict(list)  # marker_type -> [existing numeric IDs]
    unmarked_blocks: list[_UnmarkedBlock] = []

    for record in target_records:
        extractor = EXTRACTORS[record.driver](config, record, config.metamodel)
        sorted_paths = sorted(record.filepaths, key=lambda p: p.relative_to(record.record_base).as_posix())

        for filepath in sorted_paths:
            if not filepath.is_file():
                continue

            blocks = extractor.extract_blocks_from_file(filepath)

            for block in blocks:
                if not isinstance(block, TextBlock):
                    continue
                if block.marker is None:
                    continue

                # Apply marker filter
                if marker_filter and block.marker != marker_filter:
                    continue

                if block.explicit_id and block.id is not None:
                    # Check if it's a numeric ID
                    numeric = _parse_numeric_id(block.id)
                    if numeric is not None:
                        existing_ids[block.marker].append(numeric)
                elif not block.explicit_id:
                    # This block needs an ID
                    if block.source_offset is not None:
                        unmarked_blocks.append(_UnmarkedBlock(filepath=filepath, block=block))
                    else:
                        lg.warning(
                            f'Marked block [{block.marker}] in {filepath} has no source offset, skipping'
                        )

    if not unmarked_blocks:
        pprint('[green]No unmarked blocks found — nothing to renumber.[/green]')
        return

    # Phase 2: Compute next IDs per marker type
    next_ids: dict[str, int] = {}
    for marker_type in set(ub.block.marker for ub in unmarked_blocks):
        max_existing = max(existing_ids[marker_type]) if existing_ids[marker_type] else 0
        next_ids[marker_type] = max_existing + 1

    # Phase 3: Assign IDs and group by file
    # Each file is read once, all replacements computed, then written
    file_assignments: dict[Path, list[tuple[_UnmarkedBlock, int]]] = defaultdict(list)

    for ub in unmarked_blocks:
        marker_type = ub.block.marker
        new_id = next_ids[marker_type]
        next_ids[marker_type] += 1
        file_assignments[ub.filepath].append((ub, new_id))

    # Phase 4: Apply replacements per file
    modified_files = 0
    assigned_count = 0

    for filepath, assignments in file_assignments.items():
        content = filepath.read_text(encoding='utf-8')
        rel_path = config.derive_path(filepath)

        # Compute replacements for this file
        replacements: list[MarkerReplacement] = []
        for ub, new_id in assignments:
            r = _compute_tag_replacement(content, ub.block.source_offset, ub.block.marker, new_id)
            if r is None:
                lg.warning(
                    f'Could not find opening tag for [{ub.block.marker}] '
                    f'at offset {ub.block.source_offset} in {filepath}, skipping'
                )
                continue
            replacements.append(r)

        if not replacements:
            continue

        # Sort by offset descending (bottom-to-top) to avoid drift
        replacements.sort(key=lambda r: r.offset, reverse=True)

        for r in replacements:
            if dry_run:
                pprint(f'[green]DRY-RUN: Would assign [{r.marker} {r.new_id}] in {rel_path}[/green]')
            else:
                pprint(f'Assigned [{r.marker} {r.new_id}] in {rel_path}')

            # Apply replacement (bottom-to-top so offsets stay valid)
            content = content[:r.offset] + r.new_tag + content[r.offset + r.old_tag_len:]
            assigned_count += 1

        if not dry_run:
            # Write with LF line endings
            normalized = content.replace('\r\n', '\n')
            filepath.write_text(normalized, encoding='utf-8', newline='')

        modified_files += 1

    # Summary
    if dry_run:
        already_have_ids = sum(len(ids) for ids in existing_ids.values())
        pprint(f'\n[bold]Summary: {assigned_count} blocks would be renumbered, {already_have_ids} already have IDs[/bold]')
    else:
        pprint(f'\n[bold]Summary: {assigned_count} blocks renumbered across {modified_files} files[/bold]')
