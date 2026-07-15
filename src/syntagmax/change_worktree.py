# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-15
# Description: Git worktree management utilities for the change report command.

import contextlib
import logging
import os
import shutil
import stat
import time
from pathlib import Path

import git

from syntagmax.errors import FatalError

lg = logging.getLogger(__name__)


def check_git_version(repo: git.Repo) -> None:
    """Verify that the git version supports worktrees (>= 2.5)."""
    version_info = repo.git.version_info
    major = version_info[0]
    minor = version_info[1] if len(version_info) > 1 else 0

    if major < 2 or (major == 2 and minor < 5):
        version_str = '.'.join(str(v) for v in version_info)
        raise FatalError(
            f'Git version {version_str} is too old. '
            f'Worktree support requires git >= 2.5.'
        )


def check_worktrees_gitignored(repo: git.Repo, worktree_base: Path) -> None:
    """Check that the worktrees directory is listed in .gitignore.

    Raises FatalError if the worktree directory is not ignored by git,
    since committing worktree contents would corrupt the repository.
    """
    # Compute path relative to the repo working tree for check-ignore
    try:
        rel_path = worktree_base.resolve().relative_to(
            Path(repo.working_tree_dir).resolve()
        )
        worktree_dir = str(rel_path).replace('\\', '/') + '/'
    except ValueError:
        # worktree_base is outside the repo — cannot check
        worktree_dir = str(worktree_base) + '/'

    try:
        repo.git.check_ignore(worktree_dir)
    except git.GitCommandError:
        raise FatalError(
            f'The path {worktree_dir} is not ignored by git. '
            f'Please add "{worktree_dir}" to your .gitignore file '
            'to prevent worktree contents from being committed.'
        )


def resolve_revision(repo: git.Repo, rev_str: str) -> str:
    """Resolve a revision string to a full commit SHA.

    If rev_str is the sentinel 'working', returns it unchanged to indicate
    the current working tree should be used directly.
    """
    if rev_str == 'working':
        return 'working'

    try:
        commit = repo.commit(rev_str)
        return commit.hexsha
    except (git.BadName, ValueError, git.GitCommandError) as e:
        raise FatalError(
            f"Cannot resolve revision '{rev_str}': {e}"
        )


def create_worktree(
    repo: git.Repo, revision: str, label: str, worktree_base: Path
) -> Path:
    """Create a detached worktree for the given revision.

    If a stale worktree exists at the target path from a previous run,
    it is removed first.
    """
    target_path = worktree_base / label

    if target_path.exists():
        lg.debug(f'Removing stale worktree at {target_path}')
        remove_worktree(repo, target_path)

    lg.debug(f'Creating worktree for {revision[:12]} at {target_path}')
    repo.git.worktree('add', '--detach', str(target_path), revision)
    return target_path


def _handle_readonly(func, path, exc_info):
    """Error handler for shutil.rmtree to handle read-only files on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def remove_worktree(repo: git.Repo, path: Path) -> None:
    """Remove a git worktree with retry logic for Windows file locks.

    Retries up to 3 times with exponential backoff (0.5s, 1s, 2s).
    If git worktree remove fails after retries, falls back to
    shutil.rmtree with a handler for read-only files.
    """
    delays = [0.5, 1.0, 2.0]
    last_error = None

    for attempt, delay in enumerate(delays, start=1):
        try:
            repo.git.worktree('remove', '--force', str(path))
            lg.debug(f'Worktree removed via git: {path}')
            break
        except (git.GitCommandError, PermissionError, OSError) as e:
            last_error = e
            lg.debug(
                f'Worktree remove attempt {attempt}/3 failed: {e}. '
                f'Retrying in {delay}s...'
            )
            time.sleep(delay)
    else:
        lg.warning(
            f'git worktree remove failed after 3 attempts: {last_error}. '
            f'Falling back to shutil.rmtree.'
        )
        try:
            shutil.rmtree(str(path), onerror=_handle_readonly)
        except OSError as e:
            lg.warning(f'shutil.rmtree also failed for {path}: {e}')

    try:
        repo.git.worktree('prune')
    except (git.GitCommandError, OSError):
        pass


@contextlib.contextmanager
def worktree_pair(
    repo: git.Repo, base_rev: str, target_rev: str, worktree_base: Path
):
    """Context manager that provides a pair of worktree paths for comparison.

    For each revision, if the value is 'working', the current working tree
    is used directly. Otherwise a temporary detached worktree is created.

    Yields:
        Tuple of (base_path, target_path) as Path objects.
    """
    base_created = False
    target_created = False
    base_path = None
    target_path = None

    try:
        if base_rev == 'working':
            base_path = Path(repo.working_tree_dir)
        else:
            worktree_base.mkdir(parents=True, exist_ok=True)
            base_path = create_worktree(repo, base_rev, 'base', worktree_base)
            base_created = True

        if target_rev == 'working':
            target_path = Path(repo.working_tree_dir)
        else:
            worktree_base.mkdir(parents=True, exist_ok=True)
            target_path = create_worktree(
                repo, target_rev, 'target', worktree_base
            )
            target_created = True

        yield (base_path, target_path)
    finally:
        if target_created and target_path is not None:
            lg.debug(f'Cleaning up target worktree: {target_path}')
            remove_worktree(repo, target_path)

        if base_created and base_path is not None:
            lg.debug(f'Cleaning up base worktree: {base_path}')
            remove_worktree(repo, base_path)
