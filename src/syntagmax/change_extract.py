# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-15
# Description: Block extraction at a specific revision using worktree paths.

import logging
from dataclasses import replace
from pathlib import Path

from syntagmax.blocks import FileRecord
from syntagmax.config import Config, InputRecord
from syntagmax.extract import EXTRACTORS

lg = logging.getLogger(__name__)


def _remap_record(record: InputRecord, worktree_path: Path, original_base: Path) -> InputRecord:
    """Create a copy of an InputRecord with paths remapped to a worktree.

    Does NOT mutate the original record.

    The worktree contains the full repo tree. We need to find where the
    record's files live relative to the repo root, then locate them in
    the worktree at the same relative position.

    Args:
        record: Original input record from config.
        worktree_path: Path to the worktree root (same structure as repo root).
        original_base: Original base directory from config.

    Returns:
        A new InputRecord with record_base and filepaths pointing into the worktree.
    """
    # Compute how the original record_base relates to the repo root
    # The worktree IS the repo root, so we need the relative path from
    # repo root to the record's base directory.
    # Since record.record_base = original_base / record.dir, and the worktree
    # has the same structure, we need to find the relative path of record_base
    # from the repo working dir.
    try:
        # Try to get repo root from the worktree path or original base
        import git as _git
        repo = _git.Repo(worktree_path, search_parent_directories=False)
        repo_root = Path(repo.working_tree_dir).absolute()
    except Exception:
        # Fallback: the worktree IS the repo root
        repo_root = worktree_path.absolute()

    # Get the original record_base relative to original repo root
    original_record_base = record.record_base.resolve()

    # Find the relative path from the original repo root to the record base
    # The original repo root can be derived from the original_base
    # We know: original_base is config._base_dir, and repo root contains it
    try:
        original_repo = _git.Repo(original_base, search_parent_directories=True)
        original_repo_root = Path(original_repo.working_tree_dir).resolve()
        rel_to_repo = original_record_base.relative_to(original_repo_root)
    except Exception:
        # Fallback: assume record dir is relative to base
        rel_to_repo = Path(record.dir)

    new_record_base = worktree_path / rel_to_repo

    # Re-glob filepaths in the worktree using the record's configured filter
    glob_pattern = record.filter_glob

    if new_record_base.exists():
        new_filepaths = sorted(new_record_base.glob(glob_pattern))
    else:
        lg.warning('Record directory not found in worktree: %s', new_record_base)
        new_filepaths = []

    return replace(
        record,
        record_base=new_record_base,
        filepaths=new_filepaths,
    )


def _make_worktree_config(config: Config, worktree_path: Path) -> 'WorktreeConfig':
    """Create a lightweight config wrapper for extraction within a worktree.

    This avoids mutating the shared Config instance.
    """
    return WorktreeConfig(config, worktree_path)


class WorktreeConfig:
    """Lightweight config wrapper that remaps paths to a worktree.

    Provides the same interface as Config for extractors but with
    base_dir and derive_path pointing to the worktree location.
    """

    def __init__(self, original: Config, worktree_path: Path):
        self._original = original
        self._worktree_path = worktree_path
        self.params = original.params
        self.metamodel = original.metamodel
        self.metrics = original.metrics
        self.impact = original.impact
        self.ai = original.ai

        # Compute the equivalent base_dir within the worktree
        # Original base_dir is relative to repo root — same offset in worktree
        import git as _git
        try:
            original_repo = _git.Repo(original.base_dir(), search_parent_directories=True)
            original_repo_root = Path(original_repo.working_tree_dir).resolve()
            rel_base = original.base_dir().resolve().relative_to(original_repo_root)
            self._base_dir = worktree_path / rel_base
        except Exception:
            self._base_dir = worktree_path

    def base_dir(self) -> Path:
        return self._base_dir

    def derive_path(self, path: Path) -> str:
        """Derive a relative path from the worktree's base dir.

        Returns a posix-style relative path for consistent comparison
        between base and target extractions.
        """
        rel_path = path.absolute().relative_to(self._base_dir.absolute())
        return rel_path.as_posix()

    def input_records(self):
        return self._original.input_records()

    def plugins(self):
        return self._original.plugins()

    @property
    def obsidian_driver_config(self):
        return self._original.obsidian_driver_config

    def resolve_strict_line_breaks(self) -> bool:
        return self._original.resolve_strict_line_breaks()

    def load_publish_config(self, record):
        return self._original.load_publish_config(record)


def extract_blocks_at_revision(
    config: Config,
    worktree_path: Path,
    changed_files: list[str] | None = None,
) -> tuple[dict[str, list[FileRecord]], list[tuple[str, str]]]:
    """Extract blocks from files in a worktree using existing extractors.

    Args:
        config: Original project config (not mutated).
        worktree_path: Path to the worktree containing files at the target revision.
        changed_files: Optional list of relative file paths to limit extraction.
            If None, all files in each record are extracted.

    Returns:
        Tuple of:
        - Dict mapping record name to list of FileRecord objects.
        - List of (file_path, error_message) for files where extraction failed.
    """
    wt_config = _make_worktree_config(config, worktree_path)
    result: dict[str, list[FileRecord]] = {}
    errors: list[tuple[str, str]] = []

    for record in config.input_records():
        remapped = _remap_record(record, worktree_path, config.base_dir())

        if not remapped.filepaths:
            lg.debug('No files found for record %s in worktree', record.name)
            continue

        # Filter to only changed files if specified
        filepaths = remapped.filepaths
        if changed_files is not None:
            changed_set = set(changed_files)
            filepaths = [
                fp for fp in filepaths
                if _relative_posix(fp, worktree_path) in changed_set
            ]

        if not filepaths:
            lg.debug('No changed files for record %s', record.name)
            continue

        # Create extractor with the worktree config and remapped record
        extractor_cls = EXTRACTORS[remapped.driver]
        extractor = extractor_cls(wt_config, remapped, config.metamodel)

        file_records: list[FileRecord] = []
        for filepath in sorted(filepaths, key=lambda p: p.as_posix()):
            if not filepath.is_file():
                continue

            try:
                blocks = extractor.extract_blocks_from_file(filepath)
            except Exception as e:
                rel_path = _relative_posix(filepath, worktree_path)
                lg.warning('Extraction failed for %s: %s', rel_path, e)
                errors.append((rel_path, str(e)))
                continue

            if blocks:
                # Store path relative to worktree (= relative to base dir)
                rel_path = wt_config.derive_path(filepath)
                file_records.append(FileRecord(path=rel_path, blocks=blocks))

        if file_records:
            result[record.name] = file_records
            lg.debug('Extracted %d files for record %s', len(file_records), record.name)

    return result, errors


def _relative_posix(filepath: Path, base: Path) -> str:
    """Compute posix-style relative path."""
    return filepath.absolute().relative_to(base.absolute()).as_posix()
