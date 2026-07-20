# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-07-15
"""Diff computation for the change report command."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import git

if TYPE_CHECKING:
    from syntagmax.change_binary import ImageProperties

lg = logging.getLogger(__name__)


class FileStatus(Enum):
    """Status of a file in a diff."""

    ADDED = 'Added'
    REMOVED = 'Removed'
    MODIFIED = 'Modified'
    RENAMED = 'Renamed'


@dataclass
class FileDiff:
    """Represents a single file change between two commits."""

    path: str
    status: FileStatus
    old_path: str | None = None


@dataclass
class ArtifactChange:
    """Represents changes to a single artifact between two revisions."""

    aid: str
    atype: str
    changed_fields: dict  # {field_name: (old_value, new_value)}
    content_changed: bool
    base_raw_text: str
    target_raw_text: str
    file_path: str = ''


@dataclass
class ArtifactDiff:
    """Aggregate diff of artifacts between two revisions."""

    added: list  # list of tuples (aid, atype, ArtifactBlock)
    removed: list  # list of tuples (aid, atype, ArtifactBlock)
    modified: list[ArtifactChange]


@dataclass
class TextFragmentChange:
    """Represents a change to a non-artifact text fragment."""

    status: FileStatus
    file_path: str
    old_content: str | None
    new_content: str | None
    old_lines: tuple[int, int] | None
    new_lines: tuple[int, int] | None
    marker: str | None = None


@dataclass
class TextBlockDiff:
    """Aggregate diff of non-artifact text blocks between two revisions."""

    added: list[TextFragmentChange]
    removed: list[TextFragmentChange]
    modified: list[TextFragmentChange]


def get_changed_files(
    repo: git.Repo, base_hash: str, target_hash: str
) -> list[FileDiff]:
    """Compute file-level diff between two commits.

    Args:
        repo: GitPython Repo instance.
        base_hash: Hash of the base (older) commit.
        target_hash: Hash of the target (newer) commit.

    Returns:
        List of FileDiff objects describing each changed file.
    """
    base_commit = repo.commit(base_hash)
    target_commit = repo.commit(target_hash)
    diff_index = base_commit.diff(target_commit)

    results: list[FileDiff] = []

    for diff in diff_index.iter_change_type('A'):
        results.append(FileDiff(path=diff.b_path, status=FileStatus.ADDED))

    for diff in diff_index.iter_change_type('D'):
        results.append(FileDiff(path=diff.a_path, status=FileStatus.REMOVED))

    for diff in diff_index.iter_change_type('M'):
        results.append(FileDiff(path=diff.b_path, status=FileStatus.MODIFIED))

    for diff in diff_index.iter_change_type('R'):
        results.append(FileDiff(
            path=diff.b_path,
            status=FileStatus.RENAMED,
            old_path=diff.a_path,
        ))

    lg.debug('Found %d changed files between %s and %s', len(results), base_hash, target_hash)
    return results


def filter_changed_files(
    changed_files: list[FileDiff],
    input_records,
    base_dir: Path,
) -> dict[str, list[FileDiff]]:
    """Filter changed files by input record directories.

    Args:
        changed_files: List of file diffs from get_changed_files.
        input_records: List of InputRecord from syntagmax.config.
        base_dir: Base directory for resolving record paths.

    Returns:
        Dict mapping record name to list of FileDiff belonging to that record.
        Files not matching any record are excluded.
    """
    import git as _git

    # Determine repo root so we can compute record paths relative to it
    try:
        repo = _git.Repo(base_dir, search_parent_directories=True)
        repo_root = Path(repo.working_tree_dir).resolve()
    except Exception:
        repo_root = base_dir.resolve()

    result: dict[str, list[FileDiff]] = {}

    for record in input_records:
        # Compute the record's directory relative to the repo root
        record_abs = record.record_base.resolve()
        try:
            record_rel = record_abs.relative_to(repo_root).as_posix()
        except ValueError:
            # Can't make relative — skip
            continue

        matched: list[FileDiff] = []

        for file_diff in changed_files:
            file_path = file_diff.path
            # Check if the git file path starts with the record's dir prefix
            if file_path.startswith(record_rel + '/') or file_path == record_rel:
                matched.append(file_diff)

        if matched:
            result[record.name] = matched

    lg.debug('Filtered files into %d input records', len(result))
    return result


def compare_artifacts(base_records, target_records) -> ArtifactDiff:
    """Compare artifacts between base and target extraction results.

    Matches artifacts by their `aid`. Artifacts only in target are 'added',
    only in base are 'removed', and in both with differences are 'modified'.

    Args:
        base_records: list of FileRecord from base revision extraction.
        target_records: list of FileRecord from target revision extraction.

    Returns:
        ArtifactDiff with added, removed, and modified artifacts.
    """
    from syntagmax.blocks import ArtifactBlock

    # Build maps: aid -> (ArtifactBlock, file_path)
    base_map: dict[str, tuple[ArtifactBlock, str]] = {}
    for fr in base_records:
        for block in fr.blocks:
            if isinstance(block, ArtifactBlock):
                aid = block.artifact.aid
                if aid:
                    base_map[aid] = (block, fr.path)

    target_map: dict[str, tuple[ArtifactBlock, str]] = {}
    for fr in target_records:
        for block in fr.blocks:
            if isinstance(block, ArtifactBlock):
                aid = block.artifact.aid
                if aid:
                    target_map[aid] = (block, fr.path)

    added: list = []
    removed: list = []
    modified: list[ArtifactChange] = []

    # Added: in target but not in base
    for aid in target_map:
        if aid not in base_map:
            block, path = target_map[aid]
            added.append((aid, block.artifact.atype, block, path))

    # Removed: in base but not in target
    for aid in base_map:
        if aid not in target_map:
            block, path = base_map[aid]
            removed.append((aid, block.artifact.atype, block, path))

    # Modified: in both, check for differences
    for aid in base_map:
        if aid not in target_map:
            continue
        base_block, base_path = base_map[aid]
        target_block, target_path = target_map[aid]

        changed_fields = _compare_fields(
            base_block.artifact.fields,
            target_block.artifact.fields,
        )

        # Compare content (contents field, not full raw_text which includes YAML attrs)
        base_contents = base_block.artifact.fields.get('contents', '')
        target_contents = target_block.artifact.fields.get('contents', '')
        content_changed = base_contents.strip() != target_contents.strip()

        # Compare parent links
        base_pids = sorted(base_block.artifact.pids)
        target_pids = sorted(target_block.artifact.pids)
        if base_pids != target_pids:
            changed_fields['_parents'] = (base_pids, target_pids)

        if changed_fields or content_changed:
            modified.append(ArtifactChange(
                aid=aid,
                atype=base_block.artifact.atype,
                changed_fields=changed_fields,
                content_changed=content_changed,
                base_raw_text=base_contents,
                target_raw_text=target_contents,
                file_path=target_path,
            ))

    lg.debug(
        'Artifact comparison: %d added, %d removed, %d modified',
        len(added), len(removed), len(modified),
    )
    return ArtifactDiff(added=added, removed=removed, modified=modified)


def _compare_fields(
    base_fields: dict[str, str | list[str]],
    target_fields: dict[str, str | list[str]],
) -> dict:
    """Compare artifact field dicts and return only changed fields.

    Returns:
        Dict of {field_name: (old_value, new_value)}.
        Added fields: (None, new_value).
        Removed fields: (old_value, None).
        Changed fields: (old_value, new_value).
    """
    changed: dict = {}
    all_keys = set(base_fields.keys()) | set(target_fields.keys())

    for key in all_keys:
        if key == 'contents':
            # Content comparison handled separately via raw_text
            continue

        base_val = base_fields.get(key)
        target_val = target_fields.get(key)

        if base_val is None and target_val is not None:
            changed[key] = (None, target_val)
        elif base_val is not None and target_val is None:
            changed[key] = (base_val, None)
        elif base_val != target_val:
            # For list fields, compare as sorted to avoid order false-positives
            if isinstance(base_val, list) and isinstance(target_val, list):
                if sorted(str(v) for v in base_val) != sorted(str(v) for v in target_val):
                    changed[key] = (base_val, target_val)
            else:
                changed[key] = (base_val, target_val)

    return changed


def compare_text_blocks(base_records, target_records) -> TextBlockDiff:
    """Compare non-artifact text blocks between base and target extractions.

    Matches text blocks by file path and position. Uses difflib.SequenceMatcher
    for alignment within each file. Falls back to line-by-line diff for blocks
    exceeding 200 lines.

    Args:
        base_records: list of FileRecord from base revision extraction.
        target_records: list of FileRecord from target revision extraction.

    Returns:
        TextBlockDiff with added, removed, and modified text fragments.
    """
    from syntagmax.blocks import TextBlock

    MAX_LINES_FOR_SEQUENCE_MATCHER = 200

    added: list[TextFragmentChange] = []
    removed: list[TextFragmentChange] = []
    modified: list[TextFragmentChange] = []

    # Group text blocks by file path
    base_by_file: dict[str, list[TextBlock]] = {}
    for fr in base_records:
        blocks = [b for b in fr.blocks if isinstance(b, TextBlock)]
        if blocks:
            base_by_file[fr.path] = blocks

    target_by_file: dict[str, list[TextBlock]] = {}
    for fr in target_records:
        blocks = [b for b in fr.blocks if isinstance(b, TextBlock)]
        if blocks:
            target_by_file[fr.path] = blocks

    all_files = set(base_by_file.keys()) | set(target_by_file.keys())

    for file_path in sorted(all_files):
        base_blocks = base_by_file.get(file_path, [])
        target_blocks = target_by_file.get(file_path, [])

        if not base_blocks and target_blocks:
            # All blocks are new (file added or no text blocks in base)
            for i, block in enumerate(target_blocks):
                line_start = _estimate_line_number(block, target_blocks, i)
                line_count = block.content.count('\n') + 1
                added.append(TextFragmentChange(
                    status=FileStatus.ADDED,
                    file_path=file_path,
                    old_content=None,
                    new_content=block.content,
                    old_lines=None,
                    new_lines=(line_start, line_start + line_count - 1),
                    marker=block.marker,
                ))
            continue

        if base_blocks and not target_blocks:
            # All blocks removed (file removed or no text blocks in target)
            for i, block in enumerate(base_blocks):
                line_start = _estimate_line_number(block, base_blocks, i)
                line_count = block.content.count('\n') + 1
                removed.append(TextFragmentChange(
                    status=FileStatus.REMOVED,
                    file_path=file_path,
                    old_content=block.content,
                    new_content=None,
                    old_lines=(line_start, line_start + line_count - 1),
                    new_lines=None,
                    marker=block.marker,
                ))
            continue

        # Both have blocks — match by ID if available, otherwise by position
        _match_text_blocks(
            base_blocks, target_blocks, file_path,
            added, removed, modified,
            MAX_LINES_FOR_SEQUENCE_MATCHER,
        )

    lg.debug(
        'Text block comparison: %d added, %d removed, %d modified',
        len(added), len(removed), len(modified),
    )
    return TextBlockDiff(added=added, removed=removed, modified=modified)


def _match_text_blocks(
    base_blocks, target_blocks, file_path: str,
    added: list, removed: list, modified: list,
    max_lines: int,
):
    """Match text blocks between base and target within a single file."""
    import difflib
    from syntagmax.blocks import TextBlock

    # Try ID-based matching first for blocks with explicit IDs
    base_by_id: dict[str, tuple[TextBlock, int]] = {}
    target_by_id: dict[str, tuple[TextBlock, int]] = {}
    base_unmatched: list[tuple[TextBlock, int]] = []
    target_unmatched: list[tuple[TextBlock, int]] = []

    for i, block in enumerate(base_blocks):
        if block.explicit_id and block.id:
            base_by_id[block.id] = (block, i)
        else:
            base_unmatched.append((block, i))

    for i, block in enumerate(target_blocks):
        if block.explicit_id and block.id:
            target_by_id[block.id] = (block, i)
        else:
            target_unmatched.append((block, i))

    # Match by ID
    matched_base_indices: set[int] = set()
    matched_target_indices: set[int] = set()

    for block_id in base_by_id:
        if block_id in target_by_id:
            base_block, base_idx = base_by_id[block_id]
            target_block, target_idx = target_by_id[block_id]
            matched_base_indices.add(base_idx)
            matched_target_indices.add(target_idx)

            if base_block.content.strip() != target_block.content.strip():
                base_line = _estimate_line_number(base_block, base_blocks, base_idx)
                target_line = _estimate_line_number(target_block, target_blocks, target_idx)
                base_count = base_block.content.count('\n') + 1
                target_count = target_block.content.count('\n') + 1
                modified.append(TextFragmentChange(
                    status=FileStatus.MODIFIED,
                    file_path=file_path,
                    old_content=base_block.content,
                    new_content=target_block.content,
                    old_lines=(base_line, base_line + base_count - 1),
                    new_lines=(target_line, target_line + target_count - 1),
                    marker=base_block.marker,
                ))

    # ID-only additions and removals
    for block_id, (block, idx) in base_by_id.items():
        if block_id not in target_by_id:
            line_start = _estimate_line_number(block, base_blocks, idx)
            line_count = block.content.count('\n') + 1
            removed.append(TextFragmentChange(
                status=FileStatus.REMOVED,
                file_path=file_path,
                old_content=block.content,
                new_content=None,
                old_lines=(line_start, line_start + line_count - 1),
                new_lines=None,
                marker=block.marker,
            ))

    for block_id, (block, idx) in target_by_id.items():
        if block_id not in base_by_id:
            line_start = _estimate_line_number(block, target_blocks, idx)
            line_count = block.content.count('\n') + 1
            added.append(TextFragmentChange(
                status=FileStatus.ADDED,
                file_path=file_path,
                old_content=None,
                new_content=block.content,
                old_lines=None,
                new_lines=(line_start, line_start + line_count - 1),
                marker=block.marker,
            ))

    # For remaining unmatched blocks, use SequenceMatcher on content
    remaining_base = [
        (b, i) for b, i in base_unmatched if i not in matched_base_indices
    ]
    remaining_target = [
        (b, i) for b, i in target_unmatched if i not in matched_target_indices
    ]

    if not remaining_base and not remaining_target:
        return

    # Use SequenceMatcher to align remaining blocks by content similarity
    base_contents = [b.content.strip() for b, _ in remaining_base]
    target_contents = [b.content.strip() for b, _ in remaining_target]

    sm = difflib.SequenceMatcher(None, base_contents, target_contents)

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            # Same content — no change
            continue
        elif tag == 'replace':
            # Modified blocks
            for bi in range(i1, i2):
                base_block, base_idx = remaining_base[bi]
                if bi - i1 < j2 - j1:
                    # Has a corresponding target block
                    ti = j1 + (bi - i1)
                    target_block, target_idx = remaining_target[ti]
                    base_line = _estimate_line_number(base_block, base_blocks, base_idx)
                    target_line = _estimate_line_number(target_block, target_blocks, target_idx)
                    base_count = base_block.content.count('\n') + 1
                    target_count = target_block.content.count('\n') + 1
                    modified.append(TextFragmentChange(
                        status=FileStatus.MODIFIED,
                        file_path=file_path,
                        old_content=base_block.content,
                        new_content=target_block.content,
                        old_lines=(base_line, base_line + base_count - 1),
                        new_lines=(target_line, target_line + target_count - 1),
                        marker=base_block.marker,
                    ))
                else:
                    # Extra base blocks — removed
                    line_start = _estimate_line_number(base_block, base_blocks, base_idx)
                    line_count = base_block.content.count('\n') + 1
                    removed.append(TextFragmentChange(
                        status=FileStatus.REMOVED,
                        file_path=file_path,
                        old_content=base_block.content,
                        new_content=None,
                        old_lines=(line_start, line_start + line_count - 1),
                        new_lines=None,
                        marker=base_block.marker,
                    ))
            # Extra target blocks — added
            for ti in range(j1 + (i2 - i1), j2):
                target_block, target_idx = remaining_target[ti]
                line_start = _estimate_line_number(target_block, target_blocks, target_idx)
                line_count = target_block.content.count('\n') + 1
                added.append(TextFragmentChange(
                    status=FileStatus.ADDED,
                    file_path=file_path,
                    old_content=None,
                    new_content=target_block.content,
                    old_lines=None,
                    new_lines=(line_start, line_start + line_count - 1),
                    marker=target_block.marker,
                ))
        elif tag == 'delete':
            for bi in range(i1, i2):
                base_block, base_idx = remaining_base[bi]
                line_start = _estimate_line_number(base_block, base_blocks, base_idx)
                line_count = base_block.content.count('\n') + 1
                removed.append(TextFragmentChange(
                    status=FileStatus.REMOVED,
                    file_path=file_path,
                    old_content=base_block.content,
                    new_content=None,
                    old_lines=(line_start, line_start + line_count - 1),
                    new_lines=None,
                    marker=base_block.marker,
                ))
        elif tag == 'insert':
            for ti in range(j1, j2):
                target_block, target_idx = remaining_target[ti]
                line_start = _estimate_line_number(target_block, target_blocks, target_idx)
                line_count = target_block.content.count('\n') + 1
                added.append(TextFragmentChange(
                    status=FileStatus.ADDED,
                    file_path=file_path,
                    old_content=None,
                    new_content=target_block.content,
                    old_lines=None,
                    new_lines=(line_start, line_start + line_count - 1),
                    marker=target_block.marker,
                ))


def _estimate_line_number(block, all_blocks, index: int) -> int:
    """Estimate the starting line number of a text block.

    Counts newlines in preceding block contents to estimate line position.
    Uses 1-based line numbering.
    """
    # Estimate from position in block list by counting content lines
    line = 1
    for i in range(index):
        prev_block = all_blocks[i]
        if hasattr(prev_block, 'content') and prev_block.content:
            line += prev_block.content.count('\n') + 1
        elif hasattr(prev_block, 'raw_text') and prev_block.raw_text:
            line += prev_block.raw_text.count('\n') + 1
    return line



# ---------------------------------------------------------------------------
# Binary / Sidecar Artifact Comparison
# ---------------------------------------------------------------------------


@dataclass
class BinaryArtifactChange:
    """Represents changes to a sidecar-managed binary artifact."""

    aid: str
    atype: str
    file_path: str
    binary_changed: bool
    hash_base: str | None  # SHA-256 hex, None if file didn't exist
    hash_target: str | None
    base_properties: 'ImageProperties | None' = None
    target_properties: 'ImageProperties | None' = None
    field_changes: dict = field(default_factory=dict)

    @property
    def status(self) -> str:
        """Derive a human-readable status string."""
        if self.hash_base is None:
            return 'added'
        if self.hash_target is None:
            return 'removed'
        if self.binary_changed:
            return 'modified_binary'
        return 'modified_metadata'


def compare_sidecar_artifacts(
    base_records: list,
    target_records: list,
    base_path: Path,
    target_path: Path,
    base_dir_offset: Path,
) -> list[BinaryArtifactChange]:
    """Compare sidecar-managed binary artifacts between two revisions.

    Matches artifacts by `aid`. For each matched pair, computes SHA-256
    hashes of the primary file and extracts image properties when hashes
    differ. Also compares sidecar YAML fields.

    Args:
        base_records: List of FileRecord from base revision extraction.
        target_records: List of FileRecord from target revision extraction.
        base_path: Worktree path for the base revision.
        target_path: Worktree path for the target revision.
        base_dir_offset: Relative path from repo root to config.base_dir().

    Returns:
        List of BinaryArtifactChange for artifacts with binary or field changes.
    """
    from syntagmax.artifact import FileLocation
    from syntagmax.blocks import ArtifactBlock
    from syntagmax.change_binary import (
        ImageProperties,
        compute_file_hash,
        extract_image_properties,
    )

    def _is_sidecar_artifact(block) -> bool:
        """Check if a block is a sidecar-managed artifact."""
        if not isinstance(block, ArtifactBlock):
            return False
        loc = block.artifact.location
        return isinstance(loc, FileLocation) and loc.loc_sidecar is not None

    # Build maps: aid -> (ArtifactBlock, file_path)
    base_map: dict[str, tuple[ArtifactBlock, str]] = {}
    for fr in base_records:
        for block in fr.blocks:
            if _is_sidecar_artifact(block):
                aid = block.artifact.aid
                if aid:
                    base_map[aid] = (block, fr.path)

    target_map: dict[str, tuple[ArtifactBlock, str]] = {}
    for fr in target_records:
        for block in fr.blocks:
            if _is_sidecar_artifact(block):
                aid = block.artifact.aid
                if aid:
                    target_map[aid] = (block, fr.path)

    results: list[BinaryArtifactChange] = []

    # Added: in target but not in base
    for aid in target_map:
        if aid not in base_map:
            block, path = target_map[aid]
            loc_file = block.artifact.location.loc_file
            primary = target_path / base_dir_offset / loc_file
            target_hash = compute_file_hash(primary)
            target_props = extract_image_properties(primary)
            results.append(BinaryArtifactChange(
                aid=aid,
                atype=block.artifact.atype,
                file_path=path,
                binary_changed=True,
                hash_base=None,
                hash_target=target_hash,
                base_properties=None,
                target_properties=target_props,
                field_changes={},
            ))

    # Removed: in base but not in target
    for aid in base_map:
        if aid not in target_map:
            block, path = base_map[aid]
            loc_file = block.artifact.location.loc_file
            primary = base_path / base_dir_offset / loc_file
            base_hash = compute_file_hash(primary)
            base_props = extract_image_properties(primary)
            results.append(BinaryArtifactChange(
                aid=aid,
                atype=block.artifact.atype,
                file_path=path,
                binary_changed=True,
                hash_base=base_hash,
                hash_target=None,
                base_properties=base_props,
                target_properties=None,
                field_changes={},
            ))

    # Modified: in both — check for binary or field changes
    for aid in base_map:
        if aid not in target_map:
            continue
        base_block, base_file_path = base_map[aid]
        target_block, target_file_path = target_map[aid]

        # Resolve primary file paths independently (handles renames)
        base_loc_file = base_block.artifact.location.loc_file
        target_loc_file = target_block.artifact.location.loc_file

        base_primary = base_path / base_dir_offset / base_loc_file
        target_primary = target_path / base_dir_offset / target_loc_file

        # Hash comparison
        base_hash = compute_file_hash(base_primary)
        target_hash = compute_file_hash(target_primary)
        binary_changed = base_hash != target_hash

        # Extract properties only when binary content changed
        base_props: ImageProperties | None = None
        target_props: ImageProperties | None = None
        if binary_changed:
            base_props = extract_image_properties(base_primary)
            target_props = extract_image_properties(target_primary)

        # Field comparison
        field_changes = _compare_fields(
            base_block.artifact.fields,
            target_block.artifact.fields,
        )

        # Only report if something actually changed
        if binary_changed or field_changes:
            results.append(BinaryArtifactChange(
                aid=aid,
                atype=base_block.artifact.atype,
                file_path=target_file_path,
                binary_changed=binary_changed,
                hash_base=base_hash,
                hash_target=target_hash,
                base_properties=base_props,
                target_properties=target_props,
                field_changes=field_changes,
            ))

    lg.debug(
        'Sidecar comparison: %d binary artifact changes detected',
        len(results),
    )
    return results


def get_working_tree_changed_files(repo, compare_hash: str) -> list[FileDiff]:
    """Get changed files between a commit and the working tree.

    Uses git diff --name-status to compare a given revision against the
    current working directory state.
    """
    raw = repo.git.diff('--name-status', compare_hash)
    results = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        status_code = parts[0][0]  # First character: A, D, M, R
        if status_code == 'A':
            results.append(FileDiff(path=parts[1], status=FileStatus.ADDED))
        elif status_code == 'D':
            results.append(FileDiff(path=parts[1], status=FileStatus.REMOVED))
        elif status_code == 'M':
            results.append(FileDiff(path=parts[1], status=FileStatus.MODIFIED))
        elif status_code == 'R':
            results.append(FileDiff(path=parts[2] if len(parts) > 2 else parts[1], status=FileStatus.RENAMED, old_path=parts[1]))
    return results
