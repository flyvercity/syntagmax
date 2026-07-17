# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-17
# Description: Baseline tagging logic for the change baseline command.

import logging
import re
from pathlib import Path

import git

from syntagmax.config import InputRecord
from syntagmax.errors import FatalError

lg = logging.getLogger(__name__)


def discover_repos(input_records: list[InputRecord], base_dir: Path) -> dict[Path, git.Repo]:
    """Discover distinct git repositories from input records.

    Iterates over input records, finds the git repository for each record's
    base directory, deduplicates by resolved working_tree_dir, and validates
    that all repos are within the project base directory.

    Args:
        input_records: List of InputRecord objects from config.
        base_dir: The project base directory (config.base_dir()).

    Returns:
        Mapping of resolved repo_root Path → git.Repo instance.

    Raises:
        FatalError: If no repos are found, a record is not in a git repo,
                    or a repo escapes the project base directory.
    """
    repos: dict[Path, git.Repo] = {}
    errors: list[str] = []
    resolved_base = base_dir.resolve()

    for record in input_records:
        record_path = record.record_base.resolve()

        try:
            repo = git.Repo(str(record_path), search_parent_directories=True)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            errors.append(
                f'Input record "{record.name}" ({record.record_base}) '
                f'is not inside a git repository.'
            )
            continue

        repo_root = Path(repo.working_tree_dir).resolve()

        if repo_root in repos:
            continue

        # Boundary check: repo must be within or equal to base_dir
        try:
            repo_root.relative_to(resolved_base)
        except ValueError:
            errors.append(
                f'Repository at "{repo_root}" (from input record "{record.name}") '
                f'is outside the project base directory "{resolved_base}". '
                f'Refusing to tag repositories outside the project boundary.'
            )
            continue

        repos[repo_root] = repo

    if errors:
        raise FatalError(errors)

    if not repos:
        raise FatalError(['No git repositories discovered from input records.'])

    return repos


def check_repos_clean(repos: dict[Path, git.Repo]) -> None:
    """Check that all repos are clean (no dirty files, no untracked files).

    Raises:
        FatalError: If any repo is dirty, listing all dirty repos.
    """
    dirty: list[str] = []

    for repo_root, repo in repos.items():
        is_dirty = repo.is_dirty() or len(repo.untracked_files) > 0
        if is_dirty:
            dirty.append(str(repo_root))

    if dirty:
        repos_list = '\n'.join(f'  - {d}' for d in dirty)
        raise FatalError(
            [f'Cannot create baseline: the following repositories have uncommitted changes:\n{repos_list}']
        )


def validate_tag_name(tag_name: str, pattern: str | None) -> None:
    """Validate that tag_name matches the configured pattern.

    Args:
        tag_name: The tag name to validate.
        pattern: Optional regex pattern string.

    Raises:
        FatalError: If tag_name does not match the pattern.
    """
    if pattern is None:
        return

    compiled = re.compile(pattern)
    if not compiled.fullmatch(tag_name):
        raise FatalError(
            [f'Tag name "{tag_name}" does not match the configured pattern "{pattern}".']
        )


def check_tag_exists(tag_name: str, repos: dict[Path, git.Repo], force: bool) -> None:
    """Check if the tag already exists in any repo.

    Args:
        tag_name: The tag name to check.
        repos: Mapping of repo_root → Repo.
        force: If True, log warnings but do not raise.

    Raises:
        FatalError: If tag exists in any repo and force is False.
    """
    existing: list[str] = []

    for repo_root, repo in repos.items():
        if tag_name in [t.name for t in repo.tags]:
            existing.append(str(repo_root))

    if existing:
        if force:
            for repo_root_str in existing:
                repo = repos[Path(repo_root_str)]
                tag_ref = repo.tags[tag_name]
                old_commit = tag_ref.commit.hexsha[:7]
                lg.warning(
                    f'Tag "{tag_name}" already exists in {repo_root_str} '
                    f'(currently at {old_commit}). Will overwrite with --force.'
                )
        else:
            repos_list = '\n'.join(f'  - {r}' for r in existing)
            raise FatalError(
                [f'Tag "{tag_name}" already exists in the following repositories:\n{repos_list}\n'
                 f'Use --force to overwrite.']
            )


def create_baseline_tag(
    tag_name: str,
    repos: dict[Path, git.Repo],
    message: str,
    force: bool,
) -> list[tuple[Path, str]]:
    """Create annotated tags at HEAD in all repos with rollback on failure.

    Args:
        tag_name: The tag name to create.
        repos: Mapping of repo_root → Repo.
        message: Annotation message for the tag.
        force: If True, overwrite existing tags.

    Returns:
        List of (repo_root, commit_short_hash) tuples for successfully tagged repos.

    Raises:
        FatalError: If tag creation fails in any repo (after rolling back
                    tags already created in this run).
    """
    tagged: list[tuple[Path, git.Repo]] = []

    for repo_root, repo in repos.items():
        try:
            # If force and tag exists, delete it first
            if force and tag_name in [t.name for t in repo.tags]:
                old_tag = repo.tags[tag_name]
                old_commit = old_tag.commit.hexsha[:7]
                repo.delete_tag(old_tag)
                lg.warning(
                    f'Overwriting existing tag "{tag_name}" in {repo_root} '
                    f'(was at {old_commit})'
                )

            repo.create_tag(tag_name, message=message)
            tagged.append((repo_root, repo))
            lg.info(f'Created tag "{tag_name}" in {repo_root} at {repo.head.commit.hexsha[:7]}')

        except Exception as e:
            # Rollback: delete tags created in this run
            lg.error(f'Failed to create tag "{tag_name}" in {repo_root}: {e}')
            _rollback_tags(tag_name, tagged)
            raise FatalError(
                [f'Failed to create tag "{tag_name}" in {repo_root}: {e}. '
                 f'Rolled back tags in {len(tagged)} previously tagged repo(s).']
            )

    return [(root, repo.head.commit.hexsha[:7]) for root, repo in tagged]


def _rollback_tags(tag_name: str, tagged: list[tuple[Path, git.Repo]]) -> None:
    """Delete the tag from repos that were already tagged in this run."""
    for repo_root, repo in tagged:
        try:
            if tag_name in [t.name for t in repo.tags]:
                tag_ref = repo.tags[tag_name]
                repo.delete_tag(tag_ref)
                lg.warning(f'Rolled back tag "{tag_name}" from {repo_root}')
        except Exception as rollback_err:
            lg.error(f'Failed to rollback tag "{tag_name}" from {repo_root}: {rollback_err}')
