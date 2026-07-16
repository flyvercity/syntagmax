# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-07-15
# Description: Unit tests for validate_records_in_repo pre-flight check.

from dataclasses import dataclass, field
from pathlib import Path

import git
import pytest

from syntagmax.change_worktree import validate_records_in_repo
from syntagmax.errors import FatalError


@dataclass
class FakeInputRecord:
    """Minimal InputRecord stand-in for testing."""

    name: str
    dir: str
    record_base: Path
    filepaths: list = field(default_factory=list)
    driver: str = 'obsidian'
    default_atype: str = 'REQ'
    marker: str = 'REQ'
    filter_glob: str = '**/*.md'
    markers: list = field(default_factory=list)
    publish_config: str | None = None
    exclude_elements: list = field(default_factory=list)


@pytest.fixture
def repo_with_records(tmp_path):
    """Create a git repo with subdirectories suitable for input records."""
    repo_root = tmp_path / 'myrepo'
    repo_root.mkdir()
    repo = git.Repo.init(repo_root)
    # Create some subdirectories inside the repo
    (repo_root / 'REQ').mkdir()
    (repo_root / 'SYS').mkdir()
    (repo_root / 'nested' / 'deep').mkdir(parents=True)

    # Initial commit so HEAD exists
    (repo_root / '.gitkeep').write_text('', encoding='utf-8')
    repo.index.add(['.gitkeep'])
    repo.index.commit('init', author=git.Actor('Test', 'test@test.com'))
    return repo, repo_root


class TestValidateRecordsInRepo:
    """Tests for validate_records_in_repo."""

    def test_all_records_inside_repo(self, repo_with_records):
        """No error when all record base dirs are within the repo root."""
        repo, root = repo_with_records
        records = [
            FakeInputRecord(name='requirements', dir='REQ', record_base=root / 'REQ'),
            FakeInputRecord(name='system', dir='SYS', record_base=root / 'SYS'),
            FakeInputRecord(name='nested', dir='nested/deep', record_base=root / 'nested' / 'deep'),
        ]
        # Should not raise
        validate_records_in_repo(repo, records)

    def test_single_record_outside_repo(self, repo_with_records, tmp_path):
        """FatalError when one record is outside the repo."""
        repo, root = repo_with_records

        # Create a directory outside this repo (sibling, not child of repo_root)
        outside_dir = tmp_path / 'other_project' / 'docs'
        outside_dir.mkdir(parents=True)

        records = [
            FakeInputRecord(name='requirements', dir='REQ', record_base=root / 'REQ'),
            FakeInputRecord(name='external', dir='docs', record_base=outside_dir),
        ]

        with pytest.raises(FatalError) as exc_info:
            validate_records_in_repo(repo, records)

        msg = str(exc_info.value)
        assert 'external' in msg
        assert 'requirements' not in msg

    def test_all_records_outside_repo(self, repo_with_records, tmp_path):
        """FatalError lists all offending records when all are outside."""
        repo, root = repo_with_records

        outside_a = tmp_path / 'proj_a' / 'reqs'
        outside_a.mkdir(parents=True)
        outside_b = tmp_path / 'proj_b' / 'specs'
        outside_b.mkdir(parents=True)

        records = [
            FakeInputRecord(name='alpha', dir='reqs', record_base=outside_a),
            FakeInputRecord(name='beta', dir='specs', record_base=outside_b),
        ]

        with pytest.raises(FatalError) as exc_info:
            validate_records_in_repo(repo, records)

        msg = str(exc_info.value)
        assert 'alpha' in msg
        assert 'beta' in msg

    def test_empty_input_records(self, repo_with_records):
        """No error when there are no input records."""
        repo, _ = repo_with_records
        validate_records_in_repo(repo, [])

    def test_error_message_contains_repo_root(self, repo_with_records, tmp_path):
        """Error message includes the repository root path for diagnostics."""
        repo, root = repo_with_records

        outside = tmp_path / 'elsewhere'
        outside.mkdir()

        records = [
            FakeInputRecord(name='stray', dir='elsewhere', record_base=outside),
        ]

        with pytest.raises(FatalError) as exc_info:
            validate_records_in_repo(repo, records)

        msg = str(exc_info.value)
        assert 'Repository root' in msg
        assert str(root.resolve()) in msg
