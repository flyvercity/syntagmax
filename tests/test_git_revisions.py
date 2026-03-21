# SPDX-License-Identifier: MIT

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import git
from syntagmax.git_utils import populate_revisions
from syntagmax.artifact import Artifact, LineLocation, FileLocation, Revision
from syntagmax.config import Config

@pytest.fixture
def mock_config():
    config = MagicMock(spec=Config)
    config.base_dir.return_value = "/mock/repo"
    return config

@pytest.fixture
def mock_artifact(mock_config):
    artifact = Artifact(mock_config)
    artifact.atype = "REQ"
    artifact.aid = "001"
    return artifact

@patch("git.Repo")
def test_populate_revisions_line_location(mock_repo_class, mock_config, mock_artifact):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    
    mock_artifact.location = LineLocation("file.md", (1, 10))
    
    mock_commit = MagicMock()
    mock_commit.hexsha = "1234567890abcdef"
    mock_commit.committed_date = 1672531200  # 2023-01-01 00:00:00
    mock_commit.author.email = "author@example.com"
    
    # repo.blame returns list of (Commit, list of lines)
    mock_repo.blame.return_value = [(mock_commit, ["line1", "line2"])]
    
    artifacts = {"REQ-001": mock_artifact}
    populate_revisions(mock_config, artifacts)
    
    assert len(mock_artifact.revisions) == 1
    rev = list(mock_artifact.revisions)[0]
    assert rev.hash_long == "1234567890abcdef"
    assert rev.hash_short == "1234567"
    assert rev.author_email == "author@example.com"
    assert rev.timestamp == datetime.fromtimestamp(1672531200)
    
    mock_repo.blame.assert_called_once_with(None, "file.md", L="1,10")

@patch("git.Repo")
def test_populate_revisions_file_location(mock_repo_class, mock_config, mock_artifact):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    
    mock_artifact.location = FileLocation("file.md")
    
    mock_commit = MagicMock()
    mock_commit.hexsha = "abcdef1234567890"
    mock_commit.committed_date = 1672617600  # 2023-01-02 00:00:00
    mock_commit.author.email = "other@example.com"
    
    mock_repo.iter_commits.return_value = [mock_commit]
    
    artifacts = {"REQ-001": mock_artifact}
    populate_revisions(mock_config, artifacts)
    
    assert len(mock_artifact.revisions) == 1
    rev = list(mock_artifact.revisions)[0]
    assert rev.hash_long == "abcdef1234567890"
    assert rev.hash_short == "abcdef1"
    
    mock_repo.iter_commits.assert_called_once_with(paths="file.md", max_count=1)

@patch("git.Repo")
def test_populate_revisions_file_location_with_sidecar(mock_repo_class, mock_config, mock_artifact):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    
    mock_artifact.location = FileLocation("file.md", "file.md.stmx")
    
    mock_commit1 = MagicMock()
    mock_commit1.hexsha = "1111111111111111"
    mock_commit1.committed_date = 1672531200
    mock_commit1.author.email = "a1@example.com"
    
    mock_commit2 = MagicMock()
    mock_commit2.hexsha = "2222222222222222"
    mock_commit2.committed_date = 1672617600
    mock_commit2.author.email = "a2@example.com"
    
    # iter_commits will be called twice
    mock_repo.iter_commits.side_effect = [[mock_commit1], [mock_commit2]]
    
    artifacts = {"REQ-001": mock_artifact}
    populate_revisions(mock_config, artifacts)
    
    assert len(mock_artifact.revisions) == 2
    hashes = {r.hash_long for r in mock_artifact.revisions}
    assert "1111111111111111" in hashes
    assert "2222222222222222" in hashes
    
    assert mock_repo.iter_commits.call_count == 2

@patch("git.Repo")
def test_populate_revisions_invalid_repo(mock_repo_class, mock_config, mock_artifact):
    mock_repo_class.side_effect = git.InvalidGitRepositoryError
    
    mock_artifact.location = FileLocation("file.md")
    artifacts = {"REQ-001": mock_artifact}
    
    # Should not raise exception
    populate_revisions(mock_config, artifacts)
    
    assert len(mock_artifact.revisions) == 0

@patch("git.Repo")
def test_populate_revisions_exception_handling(mock_repo_class, mock_config, mock_artifact):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    
    mock_artifact.location = FileLocation("file.md")
    mock_repo.iter_commits.side_effect = Exception("Git error")
    
    artifacts = {"REQ-001": mock_artifact}
    
    # Should not raise exception
    populate_revisions(mock_config, artifacts)
    
    assert len(mock_artifact.revisions) == 0
