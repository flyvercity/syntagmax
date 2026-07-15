# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-15
# Description: Renders the change report as Markdown.

import logging
from dataclasses import dataclass, field

from syntagmax.change_diff import (
    FileDiff,
    FileStatus,
    ArtifactDiff,
    ArtifactChange,
    TextBlockDiff,
    TextFragmentChange,
)

lg = logging.getLogger(__name__)


@dataclass
class ExtractionError:
    """Represents an extraction failure for a file with fallback diff."""

    file_path: str
    error_message: str
    fallback_diff: str  # unified diff string


@dataclass
class ChangeReportData:
    """All data needed to render a change report for one input record."""

    base_revision: str
    target_revision: str
    generated_at: str  # UTC timestamp
    record_name: str
    file_diffs: list[FileDiff] = field(default_factory=list)
    artifact_diff: ArtifactDiff | None = None
    text_diff: TextBlockDiff | None = None
    extraction_errors: list[ExtractionError] = field(default_factory=list)


def compute_summary(data: ChangeReportData) -> dict[str, int]:
    """Calculate summary statistics from the change report data."""
    files_changed = 0
    files_added = 0
    files_removed = 0

    for fd in data.file_diffs:
        if fd.status == FileStatus.ADDED:
            files_added += 1
        elif fd.status == FileStatus.REMOVED:
            files_removed += 1
        else:
            files_changed += 1

    artifacts_added = 0
    artifacts_modified = 0
    artifacts_removed = 0

    if data.artifact_diff:
        artifacts_added = len(data.artifact_diff.added)
        artifacts_modified = len(data.artifact_diff.modified)
        artifacts_removed = len(data.artifact_diff.removed)

    text_fragments_modified = 0
    if data.text_diff:
        text_fragments_modified = (
            len(data.text_diff.added)
            + len(data.text_diff.removed)
            + len(data.text_diff.modified)
        )

    return {
        'files_changed': files_changed,
        'files_added': files_added,
        'files_removed': files_removed,
        'artifacts_added': artifacts_added,
        'artifacts_modified': artifacts_modified,
        'artifacts_removed': artifacts_removed,
        'text_fragments_modified': text_fragments_modified,
        'extraction_errors': len(data.extraction_errors),
    }


def _render_repo_info(data: ChangeReportData) -> list[str]:
    """Render the Repository Information section."""
    lines = [
        '## Repository Information',
        '',
        f'- **Base revision:** {data.base_revision}',
        f'- **Target revision:** {data.target_revision}',
        f'- **Generated:** {data.generated_at}',
        f'- **Input record:** {data.record_name}',
        '',
    ]
    return lines


def _render_summary(summary: dict[str, int]) -> list[str]:
    """Render the Summary section as a table."""
    lines = [
        '## Summary',
        '',
        '| Parameter | Value |',
        '|-----------|-------|',
        f'| Files changed | {summary["files_changed"]} |',
        f'| Files added | {summary["files_added"]} |',
        f'| Files removed | {summary["files_removed"]} |',
        f'| Artifacts added | {summary["artifacts_added"]} |',
        f'| Artifacts modified | {summary["artifacts_modified"]} |',
        f'| Artifacts removed | {summary["artifacts_removed"]} |',
        f'| Text fragments modified | {summary["text_fragments_modified"]} |',
    ]
    if summary['extraction_errors'] > 0:
        lines.append(f'| Extraction errors | {summary["extraction_errors"]} |')
    lines.append('')
    return lines


def _render_changed_files(data: ChangeReportData) -> list[str]:
    """Render the Changed Files overview section."""
    if not data.file_diffs:
        return []

    lines = ['## Changed Files', '']

    for fd in data.file_diffs:
        lines.append(f'### {fd.path}')
        lines.append('')
        lines.append(f'- **Status:** {fd.status.value}')
        if fd.status == FileStatus.RENAMED and fd.old_path:
            lines.append(f'- **Renamed from:** {fd.old_path}')
        lines.append('')

    return lines


def _render_artifact_added(aid: str, atype: str, block, file_path: str) -> list[str]:
    """Render an added artifact."""
    lines = [
        f'#### {atype} {aid}',
        '',
        '**Status:** Added',
        '',
    ]
    contents = block.artifact.fields.get('contents', '')
    if contents:
        lines.extend([
            '##### Text',
            '',
            '```text',
            contents,
            '```',
            '',
        ])
    # Show attributes
    attrs = {k: v for k, v in block.artifact.fields.items() if k != 'contents'}
    if attrs:
        lines.extend([
            '##### Attributes',
            '',
            '| Attribute | Value |',
            '|-----------|-------|',
        ])
        for attr_name, attr_val in attrs.items():
            lines.append(f'| {attr_name} | {_format_field_value(attr_val)} |')
        lines.append('')
    return lines


def _render_artifact_removed(aid: str, atype: str, block, file_path: str) -> list[str]:
    """Render a removed artifact."""
    lines = [
        f'#### {atype} {aid}',
        '',
        '**Status:** Removed',
        '',
    ]
    contents = block.artifact.fields.get('contents', '')
    if contents:
        lines.extend([
            '##### Text',
            '',
            '```text',
            contents,
            '```',
            '',
        ])
    return lines


def _render_artifact_modified(change: ArtifactChange) -> list[str]:
    """Render a modified artifact with text and attribute changes."""
    lines = [
        f'#### {change.atype} {change.aid}',
        '',
        '**Status:** Modified',
        '',
    ]

    # Text changes
    if change.content_changed:
        lines.extend([
            '##### Text',
            '',
            '###### Previous',
            '',
            '```text',
            change.base_raw_text.strip(),
            '```',
            '',
            '###### Current',
            '',
            '```text',
            change.target_raw_text.strip(),
            '```',
            '',
        ])

    # Attribute changes (exclude _parents for separate handling)
    field_changes = {k: v for k, v in change.changed_fields.items() if k != '_parents'}
    if field_changes:
        lines.extend([
            '##### Attribute Changes',
            '',
            '| Attribute | Previous | Current |',
            '|-----------|----------|---------|',
        ])
        for attr_name, (old_val, new_val) in field_changes.items():
            old_str = _format_field_value(old_val) if old_val is not None else '—'
            new_str = _format_field_value(new_val) if new_val is not None else '—'
            lines.append(f'| {attr_name} | {old_str} | {new_str} |')
        lines.append('')

    # Link (parent) changes
    if '_parents' in change.changed_fields:
        old_pids, new_pids = change.changed_fields['_parents']
        lines.extend([
            '##### Link Changes',
            '',
            '| Attribute | Previous | Current |',
            '|-----------|----------|---------|',
            f'| parents | {", ".join(old_pids) if old_pids else "—"} | {", ".join(new_pids) if new_pids else "—"} |',
            '',
        ])

    return lines


def _render_text_fragment(change: TextFragmentChange) -> list[str]:
    """Render a single text fragment change."""
    lines = ['#### Text fragment', '']

    lines.append(f'**Status:** {change.status.value}')
    lines.append('')

    if change.old_lines:
        lines.append(f'- **Old lines:** {change.old_lines[0]}-{change.old_lines[1]}')
    if change.new_lines:
        lines.append(f'- **New lines:** {change.new_lines[0]}-{change.new_lines[1]}')
    if change.old_lines or change.new_lines:
        lines.append('')

    if change.status == FileStatus.ADDED:
        if change.new_content:
            lines.extend(['```text', change.new_content.strip(), '```', ''])
    elif change.status == FileStatus.REMOVED:
        if change.old_content:
            lines.extend([
                '##### Previous', '',
                '```text', change.old_content.strip(), '```', '',
            ])
    else:
        # Modified
        if change.old_content:
            lines.extend([
                '##### Previous', '',
                '```text', change.old_content.strip(), '```', '',
            ])
        if change.new_content:
            lines.extend([
                '##### Current', '',
                '```text', change.new_content.strip(), '```', '',
            ])

    return lines


def _render_extraction_error(error: ExtractionError) -> list[str]:
    """Render a single extraction error with fallback diff."""
    lines = [
        f'### {error.file_path}',
        '',
        '\u26a0\ufe0f **Extraction Error**',
        '',
        error.error_message,
        '',
        'Fallback plain-text diff:',
        '',
        '```diff',
        error.fallback_diff,
        '```',
        '',
    ]
    return lines


def _render_detailed_changes(data: ChangeReportData) -> list[str]:
    """Render the Detailed Changes section."""
    lines = ['## Detailed Changes', '']

    has_content = False

    # Render artifact changes
    if data.artifact_diff:
        # Added artifacts
        for aid, atype, block, file_path in data.artifact_diff.added:
            has_content = True
            lines.extend(_render_artifact_added(aid, atype, block, file_path))

        # Modified artifacts
        for change in data.artifact_diff.modified:
            has_content = True
            lines.extend(_render_artifact_modified(change))

        # Removed artifacts
        for aid, atype, block, file_path in data.artifact_diff.removed:
            has_content = True
            lines.extend(_render_artifact_removed(aid, atype, block, file_path))

    # Render text block changes
    if data.text_diff:
        all_text_changes = (
            data.text_diff.added + data.text_diff.modified + data.text_diff.removed
        )
        for change in all_text_changes:
            has_content = True
            lines.extend(_render_text_fragment(change))

    # Extraction errors
    if data.extraction_errors:
        has_content = True
        for error in data.extraction_errors:
            lines.extend(_render_extraction_error(error))

    if not has_content:
        lines.append('No changes detected.')
        lines.append('')

    return lines


def _format_field_value(val) -> str:
    """Format a field value for display in a table cell."""
    if val is None:
        return '—'
    if isinstance(val, list):
        return ', '.join(str(v) for v in val)
    return str(val)


def render_change_report(data: ChangeReportData) -> str:
    """Build the full markdown change report.

    Args:
        data: The change report data containing all diffs and metadata.

    Returns:
        A complete Markdown report string.
    """
    lines: list[str] = []

    # Title
    lines.extend(['# Change Report', '', '---', ''])

    # Repository Information
    lines.extend(_render_repo_info(data))
    lines.extend(['---', ''])

    # Summary
    summary = compute_summary(data)
    lines.extend(_render_summary(summary))
    lines.extend(['---', ''])

    # Changed Files
    changed_files_section = _render_changed_files(data)
    if changed_files_section:
        lines.extend(changed_files_section)
        lines.extend(['---', ''])

    # Detailed Changes
    lines.extend(_render_detailed_changes(data))

    return '\n'.join(lines)
