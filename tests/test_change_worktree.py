# SPDX-License-Identifier: MIT
# Author: Boris Resnick (Tested by Jules)
# Created: 2026-07-15
# Description: Unit and integration tests for change_worktree.py utilities.

import logging
import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import git
import pytest

from syntagmax.change_worktree import (
    _handle_readonly,
    check_git_version,
    check_worktrees_gitignored,
    create_worktree,
    remove_worktree,
    resolve_revision,
    worktree_pair,
)
from syntagmax.errors import FatalError


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=git.Repo)
    repo.git = MagicMock()
    repo.working_tree_dir = "/mock/repo/root"
    return repo


class TestCheckGitVersion:
    def test_git_version_supported(self, mock_repo):
        # >= 2.5
        mock_repo.git.version_info = (2, 5, 0)
        check_git_version(mock_repo)  # Should not raise

        mock_repo.git.version_info = (2, 30, 1)
        check_git_version(mock_repo)  # Should not raise

        mock_repo.git.version_info = (3, 0)
        check_git_version(mock_repo)  # Should not raise

    def test_git_version_unsupported(self, mock_repo):
        # < 2.5
        mock_repo.git.version_info = (2, 4, 9)
        with pytest.raises(FatalError) as exc_info:
            check_git_version(mock_repo)
        assert "is too old" in str(exc_info.value)
        assert "requires git >= 2.5" in str(exc_info.value)

        mock_repo.git.version_info = (1, 9, 5)
        with pytest.raises(FatalError) as exc_info:
            check_git_version(mock_repo)
        assert "requires git >= 2.5" in str(exc_info.value)

        mock_repo.git.version_info = (2,)
        with pytest.raises(FatalError) as exc_info:
            check_git_version(mock_repo)
        assert "requires git >= 2.5" in str(exc_info.value)


class TestCheckWorktreesGitignored:
    def test_gitignored_success(self, mock_repo):
        mock_repo.working_tree_dir = "/mock/repo"
        # Mock resolve relative_to behaviour
        with patch.object(Path, "resolve") as mock_resolve:
            # We want: resolve().relative_to(resolve()) -> "worktrees"
            # Let's mock resolve to return a specific Path mock
            mock_path = MagicMock(spec=Path)
            mock_path.relative_to.return_value = "worktrees"
            mock_resolve.return_value = mock_path

            # Should not raise
            check_worktrees_gitignored(mock_repo, Path("/mock/repo/worktrees"))
            mock_repo.git.check_ignore.assert_called_once_with("worktrees/")

    def test_gitignored_outside_repo(self, mock_repo):
        mock_repo.working_tree_dir = "/mock/repo"
        # check_worktrees_gitignored uses resolve().relative_to().
        # If relative_to raises ValueError, it falls back to str(worktree_base) + '/'
        with patch.object(Path, "resolve") as mock_resolve:
            mock_path = MagicMock(spec=Path)
            mock_path.relative_to.side_effect = ValueError("Outside")
            mock_resolve.return_value = mock_path

            check_worktrees_gitignored(mock_repo, Path("/outside/worktrees"))
            mock_repo.git.check_ignore.assert_called_once_with("/outside/worktrees/")

    def test_not_gitignored_raises_error(self, mock_repo):
        mock_repo.working_tree_dir = "/mock/repo"
        mock_repo.git.check_ignore.side_effect = git.GitCommandError("check-ignore", 1)

        with patch.object(Path, "resolve") as mock_resolve:
            mock_path = MagicMock(spec=Path)
            mock_path.relative_to.return_value = "worktrees"
            mock_resolve.return_value = mock_path

            with pytest.raises(FatalError) as exc_info:
                check_worktrees_gitignored(mock_repo, Path("/mock/repo/worktrees"))
            assert "is not ignored by git" in str(exc_info.value)
            assert "Please add" in str(exc_info.value)


class TestResolveRevision:
    def test_resolve_working(self, mock_repo):
        assert resolve_revision(mock_repo, "working") == "working"

    def test_resolve_valid_sha(self, mock_repo):
        mock_commit = MagicMock()
        mock_commit.hexsha = "abcdef1234567890"
        mock_repo.commit.return_value = mock_commit

        assert resolve_revision(mock_repo, "main") == "abcdef1234567890"
        mock_repo.commit.assert_called_once_with("main")

    @pytest.mark.parametrize(
        "exception",
        [
            git.BadName("bad name"),
            ValueError("value error"),
            git.GitCommandError("commit", 1),
        ],
    )
    def test_resolve_invalid_revisions(self, mock_repo, exception):
        mock_repo.commit.side_effect = exception
        with pytest.raises(FatalError) as exc_info:
            resolve_revision(mock_repo, "invalid-rev")
        assert "Cannot resolve revision 'invalid-rev'" in str(exc_info.value)


class TestCreateWorktree:
    def test_create_worktree_fresh(self, mock_repo, tmp_path):
        worktree_base = tmp_path / "worktrees"
        target_path = worktree_base / "my-label"

        # Ensure target doesn't exist initially
        assert not target_path.exists()

        res_path = create_worktree(mock_repo, "sha123", "my-label", worktree_base)

        assert res_path == target_path
        mock_repo.git.worktree.assert_called_once_with(
            "add", "--detach", str(target_path), "sha123"
        )

    def test_create_worktree_stale_exists(self, mock_repo, tmp_path):
        worktree_base = tmp_path / "worktrees"
        target_path = worktree_base / "my-label"
        target_path.mkdir(parents=True)

        with patch("syntagmax.change_worktree.remove_worktree") as mock_remove:
            res_path = create_worktree(mock_repo, "sha123", "my-label", worktree_base)
            assert res_path == target_path
            mock_remove.assert_called_once_with(mock_repo, target_path)
            mock_repo.git.worktree.assert_called_once_with(
                "add", "--detach", str(target_path), "sha123"
            )


class TestRemoveWorktreeAndHelper:
    def test_handle_readonly(self):
        mock_func = MagicMock()
        with patch("os.chmod") as mock_chmod:
            _handle_readonly(mock_func, "/some/path", None)
            mock_chmod.assert_called_once_with("/some/path", stat.S_IWRITE)
            mock_func.assert_called_once_with("/some/path")

    def test_handle_readonly_os_error_is_caught(self):
        mock_func = MagicMock()
        with patch("os.chmod", side_effect=OSError("Permission denied")):
            # Should catch OSError and not raise
            _handle_readonly(mock_func, "/some/path", None)
            mock_func.assert_not_called()

    @patch("time.sleep")
    def test_remove_worktree_success_first_try(self, mock_sleep, mock_repo, tmp_path):
        path = tmp_path / "worktree"
        remove_worktree(mock_repo, path)

        mock_repo.git.worktree.assert_any_call("remove", "--force", str(path))
        mock_repo.git.worktree.assert_any_call("prune")
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_remove_worktree_success_retry(self, mock_sleep, mock_repo, tmp_path):
        path = tmp_path / "worktree"
        # 1st try fails, 2nd succeeds
        mock_repo.git.worktree.side_effect = [
            git.GitCommandError("worktree", 1),  # remove 1st
            None,                               # remove 2nd
            None,                               # prune
        ]

        remove_worktree(mock_repo, path)

        assert mock_repo.git.worktree.call_count == 3  # remove, remove, prune
        mock_sleep.assert_called_once_with(0.5)

    @patch("shutil.rmtree")
    @patch("time.sleep")
    def test_remove_worktree_fallback_to_rmtree(self, mock_sleep, mock_rmtree, mock_repo, tmp_path):
        path = tmp_path / "worktree"
        # All 3 attempts fail
        mock_repo.git.worktree.side_effect = git.GitCommandError("worktree", 1)

        remove_worktree(mock_repo, path)

        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(0.5)
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

        mock_rmtree.assert_called_once_with(str(path), onerror=_handle_readonly)
        # Prune is still attempted
        mock_repo.git.worktree.assert_any_call("prune")

    @patch("shutil.rmtree")
    @patch("time.sleep")
    def test_remove_worktree_rmtree_fails(self, mock_sleep, mock_rmtree, mock_repo, tmp_path, caplog):
        path = tmp_path / "worktree"
        mock_repo.git.worktree.side_effect = OSError("Lock error")
        mock_rmtree.side_effect = OSError("Fatal delete error")

        # Should not raise, but log warning
        with caplog.at_level(logging.WARNING):
            remove_worktree(mock_repo, path)

        assert any("shutil.rmtree also failed" in r.message for r in caplog.records)


class TestWorktreePairContextManager:
    def test_both_working(self, mock_repo, tmp_path):
        mock_repo.working_tree_dir = "/mock/repo"
        with patch("syntagmax.change_worktree.create_worktree") as mock_create, \
             patch("syntagmax.change_worktree.remove_worktree") as mock_remove:

            with worktree_pair(mock_repo, "working", "working", tmp_path) as (base, target):
                assert base == Path("/mock/repo")
                assert target == Path("/mock/repo")

            mock_create.assert_not_called()
            mock_remove.assert_not_called()

    def test_create_and_cleanup_worktrees(self, mock_repo, tmp_path):
        mock_repo.working_tree_dir = "/mock/repo"
        base_path = tmp_path / "base"
        target_path = tmp_path / "target"

        def mock_create_impl(repo, rev, label, base_dir):
            if label == "base":
                return base_path
            return target_path

        with patch("syntagmax.change_worktree.create_worktree", side_effect=mock_create_impl) as mock_create, \
             patch("syntagmax.change_worktree.remove_worktree") as mock_remove:

            with worktree_pair(mock_repo, "sha-base", "sha-target", tmp_path) as (base, target):
                assert base == base_path
                assert target == target_path
                assert mock_create.call_count == 2
                mock_remove.assert_not_called()  # Not yet cleaned up inside the with-block

            # Cleanup should occur in reverse order or standard cleanup
            mock_remove.assert_any_call(mock_repo, target_path)
            mock_remove.assert_any_call(mock_repo, base_path)
            assert mock_remove.call_count == 2

    def test_cleanup_on_exception(self, mock_repo, tmp_path):
        mock_repo.working_tree_dir = "/mock/repo"
        base_path = tmp_path / "base"
        target_path = tmp_path / "target"

        def mock_create_impl(repo, rev, label, base_dir):
            if label == "base":
                return base_path
            return target_path

        with patch("syntagmax.change_worktree.create_worktree", side_effect=mock_create_impl), \
             patch("syntagmax.change_worktree.remove_worktree") as mock_remove:

            with pytest.raises(ValueError, match="Inside error"):
                with worktree_pair(mock_repo, "sha-base", "sha-target", tmp_path) as (base, target):
                    raise ValueError("Inside error")

            # Even if error is raised inside, both created worktrees must be cleaned up
            mock_remove.assert_any_call(mock_repo, target_path)
            mock_remove.assert_any_call(mock_repo, base_path)
            assert mock_remove.call_count == 2
