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
    BinaryArtifactChange,
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
    binary_diff: list[BinaryArtifactChange] = field(default_factory=list)
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

    binary_added = 0
    binary_modified = 0
    binary_removed = 0
    for bc in data.binary_diff:
        status = bc.status
        if status == 'added':
            binary_added += 1
        elif status == 'removed':
            binary_removed += 1
        else:
            binary_modified += 1

    return {
        'files_changed': files_changed,
        'files_added': files_added,
        'files_removed': files_removed,
        'artifacts_added': artifacts_added,
        'artifacts_modified': artifacts_modified,
        'artifacts_removed': artifacts_removed,
        'text_fragments_modified': text_fragments_modified,
        'binary_added': binary_added,
        'binary_modified': binary_modified,
        'binary_removed': binary_removed,
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
    # Binary artifact stats (only show if any exist)
    binary_total = summary['binary_added'] + summary['binary_modified'] + summary['binary_removed']
    if binary_total > 0:
        lines.append(f'| Binary artifacts added | {summary["binary_added"]} |')
        lines.append(f'| Binary artifacts modified | {summary["binary_modified"]} |')
        lines.append(f'| Binary artifacts removed | {summary["binary_removed"]} |')
    if summary['extraction_errors'] > 0:
        lines.append(f'| Extraction errors | {summary["extraction_errors"]} |')
    lines.append('')
    return lines


def _normalize_binary_status(status: str) -> str:
    """Normalise binary artefact status strings to title-case labels."""
    mapping = {
        'added': 'Added',
        'removed': 'Removed',
        'modified_binary': 'Modified',
        'modified_metadata': 'Modified',
    }
    return mapping.get(status, status.title())


def _build_objects_by_file(data: ChangeReportData) -> dict[str, list[tuple[str, str, str]]]:
    """Build a mapping of file path → list of (aid, atype, status) for all artefacts.

    Combines both regular artefact changes and binary artefact changes.
    This is separate from _group_artifacts_by_file to avoid affecting
    render_summary_report (R4 isolation).
    """
    result: dict[str, list[tuple[str, str, str]]] = {}

    if data.artifact_diff:
        for aid, atype, _block, file_path in data.artifact_diff.added:
            result.setdefault(file_path, []).append((aid, atype, 'Added'))

        for change in data.artifact_diff.modified:
            result.setdefault(change.file_path, []).append(
                (change.aid, change.atype, 'Modified')
            )

        for aid, atype, _block, file_path in data.artifact_diff.removed:
            result.setdefault(file_path, []).append((aid, atype, 'Removed'))

    if data.binary_diff:
        for bc in data.binary_diff:
            status_label = _normalize_binary_status(bc.status)
            result.setdefault(bc.file_path, []).append((bc.aid, bc.atype, status_label))

    return result


def _render_changed_files(data: ChangeReportData) -> list[str]:
    """Render the Changed Files overview section as a table."""
    if not data.file_diffs:
        return []

    objects_by_file = _build_objects_by_file(data)

    lines = [
        '## Changed Files',
        '',
        '| Filename | Status | Objects changed |',
        '|----------|--------|-----------------|',
    ]

    for fd in data.file_diffs:
        if fd.status == FileStatus.RENAMED and fd.old_path:
            status_str = f'Renamed (from {fd.old_path})'
        else:
            status_str = fd.status.value

        # Look up artefacts for this file using suffix matching
        file_objects = _match_file_path(fd.path, objects_by_file)
        if file_objects:
            objects_str = ', '.join(
                f'{aid} ({status})' for aid, _atype, status in file_objects
            )
        else:
            objects_str = '—'

        lines.append(f'| {fd.path} | {status_str} | {objects_str} |')

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
        ])
        lines.extend(_blockquote_content(contents))
        lines.append('')
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
        ])
        lines.extend(_blockquote_content(contents))
        lines.append('')
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
        ])
        lines.extend(_blockquote_content(change.base_raw_text.strip()))
        lines.append('')
        lines.extend([
            '###### Current',
            '',
        ])
        lines.extend(_blockquote_content(change.target_raw_text.strip()))
        lines.append('')

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
            lines.extend(_blockquote_content(change.new_content.strip()))
            lines.append('')
    elif change.status == FileStatus.REMOVED:
        if change.old_content:
            lines.extend(['##### Previous', ''])
            lines.extend(_blockquote_content(change.old_content.strip()))
            lines.append('')
    else:
        # Modified
        if change.old_content:
            lines.extend(['##### Previous', ''])
            lines.extend(_blockquote_content(change.old_content.strip()))
            lines.append('')
        if change.new_content:
            lines.extend(['##### Current', ''])
            lines.extend(_blockquote_content(change.new_content.strip()))
            lines.append('')

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


def _render_binary_artifact_change(change: BinaryArtifactChange) -> list[str]:
    """Render a single binary artifact change."""
    from syntagmax.change_binary import format_file_size

    status = change.status
    if status == 'added':
        status_label = 'Added (binary)'
    elif status == 'removed':
        status_label = 'Removed (binary)'
    elif status == 'modified_binary':
        status_label = 'Modified (binary)'
    else:
        status_label = 'Modified (metadata)'

    lines = [
        f'#### {change.atype} {change.aid}',
        '',
        f'**Status:** {status_label}',
        '',
    ]

    # Binary content property table — only when binary content changed
    if change.binary_changed:
        lines.extend([
            '##### Binary Content',
            '',
            '| Property | Previous | Current |',
            '|----------|----------|---------|',
        ])

        # SHA-256 row (truncated to 12 chars)
        base_hash = f'`{change.hash_base[:12]}`' if change.hash_base else '—'
        target_hash = f'`{change.hash_target[:12]}`' if change.hash_target else '—'
        lines.append(f'| SHA-256 | {base_hash} | {target_hash} |')

        # Size row
        base_size = format_file_size(change.base_properties.size_bytes) if change.base_properties else '—'
        target_size = format_file_size(change.target_properties.size_bytes) if change.target_properties else '—'
        lines.append(f'| Size | {base_size} | {target_size} |')

        # Dimensions row — only if at least one revision has dimensions
        base_w = change.base_properties.width if change.base_properties else None
        target_w = change.target_properties.width if change.target_properties else None
        if base_w is not None or target_w is not None:
            if change.base_properties and change.base_properties.width is not None:
                base_dims = f'{change.base_properties.width}×{change.base_properties.height}'
            else:
                base_dims = '—'
            if change.target_properties and change.target_properties.width is not None:
                target_dims = f'{change.target_properties.width}×{change.target_properties.height}'
            else:
                target_dims = '—'
            lines.append(f'| Dimensions | {base_dims} | {target_dims} |')

        lines.append('')

    # Attribute changes table
    if change.field_changes:
        lines.extend([
            '##### Attribute Changes',
            '',
            '| Attribute | Previous | Current |',
            '|-----------|----------|---------|',
        ])
        for attr_name, (old_val, new_val) in change.field_changes.items():
            old_str = _format_field_value(old_val) if old_val is not None else '—'
            new_str = _format_field_value(new_val) if new_val is not None else '—'
            lines.append(f'| {attr_name} | {old_str} | {new_str} |')
        lines.append('')

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

    # Render binary artifact changes
    if data.binary_diff:
        for bc in data.binary_diff:
            has_content = True
            lines.extend(_render_binary_artifact_change(bc))

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


def _blockquote_content(text: str) -> list[str]:
    """Convert text to blockquoted lines with headers escaped.

    - Each line is prefixed with '> '.
    - Lines starting with '#' outside of fenced code blocks are escaped:
      '# Foo' → '\\# Foo'.
    - Lines inside fenced code blocks (``` markers) are left untouched.
    """
    if not text or not text.strip():
        return []
    lines = []
    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block

        # Only escape headers outside code blocks
        if not in_code_block and line.lstrip().startswith('#'):
            idx = len(line) - len(line.lstrip())
            line = line[:idx] + '\\' + line[idx:]

        lines.append(f'> {line}')
    return lines


def _format_field_value(val) -> str:
    """Format a field value for display in a table cell, handling newlines and pipes."""
    if val is None:
        return '—'

    def _format_single(v) -> str:
        s = str(v)
        if '\n' in s:
            first_line = next((ln for ln in s.splitlines() if ln.strip()), s.splitlines()[0])
            s = f'{first_line.strip()} …'
        s = s.replace('|', '\\|')
        # Wrap in backticks if value contains angle brackets to prevent HTML interpretation
        if '<' in s and '>' in s:
            s = f'`{s}`'
        return s

    if isinstance(val, list):
        return ', '.join(_format_single(v) for v in val)
    return _format_single(val)


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



# ---------------------------------------------------------------------------
# Summary Report Rendering
# ---------------------------------------------------------------------------


def _format_line_range(start: int, end: int) -> str:
    """Format a line range as a compact string.

    Single-line ranges omit the separator (e.g. 'lines 45' not 'lines 45–45').
    """
    if start == end:
        return f'lines {start}'
    return f'lines {start}\u2013{end}'


def _format_text_fragment_entry(change: TextFragmentChange) -> str:
    """Format a text fragment change as a compact line description.

    Examples:
        'Modified (lines 45–52 → 45–56)'
        'Added (lines 128)'
        'Removed (lines 210–218)'
    """
    status = change.status.value

    if change.status == FileStatus.MODIFIED:
        old_range = _format_line_range(*change.old_lines) if change.old_lines else '?'
        new_range = _format_line_range(*change.new_lines) if change.new_lines else '?'
        return f'{status} ({old_range} \u2192 {new_range})'
    elif change.status == FileStatus.ADDED:
        new_range = _format_line_range(*change.new_lines) if change.new_lines else '?'
        return f'{status} ({new_range})'
    else:
        # Removed
        old_range = _format_line_range(*change.old_lines) if change.old_lines else '?'
        return f'{status} ({old_range})'


def _group_artifacts_by_file(
    data: ChangeReportData,
) -> dict[str, list[tuple[str, str, str]]]:
    """Group artefact changes by file path.

    Returns:
        Dict mapping file_path -> list of (aid, atype, status_str).
    """
    result: dict[str, list[tuple[str, str, str]]] = {}

    if not data.artifact_diff:
        return result

    for aid, atype, _block, file_path in data.artifact_diff.added:
        result.setdefault(file_path, []).append((aid, atype, 'Added'))

    for change in data.artifact_diff.modified:
        result.setdefault(change.file_path, []).append(
            (change.aid, change.atype, 'Modified')
        )

    for aid, atype, _block, file_path in data.artifact_diff.removed:
        result.setdefault(file_path, []).append((aid, atype, 'Removed'))

    return result


def _group_text_fragments_by_file(
    data: ChangeReportData,
) -> dict[str, list[str]]:
    """Group text fragment changes by file path.

    Returns:
        Dict mapping file_path -> list of formatted line descriptions.
    """
    result: dict[str, list[str]] = {}

    if not data.text_diff:
        return result

    all_changes = (
        data.text_diff.added + data.text_diff.modified + data.text_diff.removed
    )
    for change in all_changes:
        entry = _format_text_fragment_entry(change)
        result.setdefault(change.file_path, []).append(entry)

    return result


def _match_file_path(fd_path: str, path_map: dict) -> list:
    """Match a file diff path against artifact/fragment keys.

    The file diff path is relative to the repo root, while extraction paths
    are relative to the config's base_dir. We match by checking if the
    diff path ends with the artifact path or vice versa.
    """
    # Exact match first
    if fd_path in path_map:
        return path_map[fd_path]

    # Try suffix matching: the shorter path should be a suffix of the longer
    for key, value in path_map.items():
        if fd_path.endswith('/' + key) or fd_path == key:
            return value
        if key.endswith('/' + fd_path) or key == fd_path:
            return value

    return []


def _render_summary_changed_files(
    data: ChangeReportData,
    artifacts_by_file: dict[str, list[tuple[str, str, str]]],
    fragments_by_file: dict[str, list[str]],
) -> list[str]:
    """Render per-file breakdown for the summary report."""
    lines = ['## Changed Files', '']

    has_content = False

    for fd in data.file_diffs:
        has_content = True
        lines.append(f'### {fd.path}')
        lines.append('')

        # Status line
        if fd.status == FileStatus.RENAMED and fd.old_path:
            lines.append(f'Status: Renamed (from {fd.old_path})')
        else:
            lines.append(f'Status: {fd.status.value}')
        lines.append('')

        # Objects — match using suffix-aware lookup
        file_artifacts = _match_file_path(fd.path, artifacts_by_file)
        if file_artifacts:
            lines.append('**Objects**')
            lines.append('')
            for aid, atype, status in file_artifacts:
                lines.append(f'- {atype} {aid} ({status})')
            lines.append('')

        # Text fragments — match using suffix-aware lookup
        file_fragments = _match_file_path(fd.path, fragments_by_file)
        if file_fragments:
            lines.append('**Text fragments**')
            lines.append('')
            for entry in file_fragments:
                lines.append(f'- {entry}')
            lines.append('')

    # Extraction errors (show file path + error message, no fallback diff)
    if data.extraction_errors:
        for error in data.extraction_errors:
            has_content = True
            lines.append(f'### {error.file_path}')
            lines.append('')
            lines.append('Status: Error')
            lines.append('')
            lines.append(error.error_message)
            lines.append('')

    if not has_content:
        lines.append('No changes detected.')
        lines.append('')

    return lines


def render_summary_report(data: ChangeReportData) -> str:
    """Build an abbreviated summary change report.

    The summary report shows which files, artefacts, and text fragments
    changed, without displaying content, attribute diffs, or OLD/NEW blocks.

    Args:
        data: The change report data (same structure as for the full report).

    Returns:
        A complete Markdown summary report string.
    """
    lines: list[str] = []

    # Title
    lines.extend(['# Change Report (Summary)', '', '---', ''])

    # Repository Information (reuse existing helper)
    lines.extend(_render_repo_info(data))
    lines.extend(['---', ''])

    # Summary statistics (reuse existing helper)
    summary = compute_summary(data)
    lines.extend(_render_summary(summary))
    lines.extend(['---', ''])

    # Per-file breakdown
    artifacts_by_file = _group_artifacts_by_file(data)
    fragments_by_file = _group_text_fragments_by_file(data)
    lines.extend(_render_summary_changed_files(
        data, artifacts_by_file, fragments_by_file,
    ))

    return '\n'.join(lines)
