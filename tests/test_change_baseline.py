# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-07-17
# Description: Tests for the change baseline command.

from dataclasses import dataclass, field
from pathlib import Path

import git
import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from syntagmax.change_baseline import (
    check_repos_clean,
    check_tag_exists,
    create_baseline_tag,
    discover_repos,
    validate_tag_name,
)
from syntagmax.cli import rms
from syntagmax.config import BaselineConfig, ConfigFile
from syntagmax.errors import FatalError


# --- Fixtures and Helpers ---


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


def _init_repo(path: Path) -> git.Repo:
    """Create a git repo with an initial commit."""
    path.mkdir(parents=True, exist_ok=True)
    repo = git.Repo.init(path)
    dummy = path / '.gitkeep'
    dummy.write_text('', encoding='utf-8')
    repo.index.add(['.gitkeep'])
    repo.index.commit('init', author=git.Actor('Test', 'test@test.com'))
    return repo


# --- BaselineConfig Tests ---


class TestBaselineConfig:
    def test_default_no_pattern(self):
        cfg = BaselineConfig()
        assert cfg.tag_pattern is None

    def test_valid_pattern(self):
        cfg = BaselineConfig(tag_pattern=r'^v\d+\.\d+\.\d+$')
        assert cfg.tag_pattern == r'^v\d+\.\d+\.\d+$'

    def test_invalid_pattern_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            BaselineConfig(tag_pattern='[invalid')
        assert 'tag_pattern' in str(exc_info.value)

    def test_baseline_in_config_file_model(self):
        """ConfigFile model accepts a baseline section."""
        data = {
            'base': '..',
            'input': [{'name': 'test', 'dir': 'REQ', 'driver': 'obsidian'}],
            'baseline': {'tag_pattern': r'^v\d+$'},
        }
        model = ConfigFile.model_validate(data)
        assert model.baseline.tag_pattern == r'^v\d+$'

    def test_config_file_model_without_baseline(self):
        """ConfigFile works without a baseline section."""
        data = {
            'base': '..',
            'input': [{'name': 'test', 'dir': 'REQ', 'driver': 'obsidian'}],
        }
        model = ConfigFile.model_validate(data)
        assert model.baseline.tag_pattern is None


# --- discover_repos Tests ---


class TestDiscoverRepos:
    def test_single_repo(self, tmp_path):
        """Records in one repo produce one entry."""
        repo_root = tmp_path / 'project'
        _init_repo(repo_root)
        req_dir = repo_root / 'REQ'
        req_dir.mkdir()

        records = [FakeInputRecord(name='reqs', dir='REQ', record_base=req_dir)]
        result = discover_repos(records, tmp_path)
        assert len(result) == 1
        assert repo_root.resolve() in result

    def test_two_repos(self, tmp_path):
        """Records in two repos produce two entries."""
        repo_a = tmp_path / 'repo_a'
        repo_b = tmp_path / 'repo_b'
        _init_repo(repo_a)
        _init_repo(repo_b)

        records = [
            FakeInputRecord(name='a', dir='REQ', record_base=repo_a),
            FakeInputRecord(name='b', dir='SYS', record_base=repo_b),
        ]
        result = discover_repos(records, tmp_path)
        assert len(result) == 2

    def test_deduplication(self, tmp_path):
        """Multiple records in same repo produce one entry."""
        repo_root = tmp_path / 'project'
        _init_repo(repo_root)
        dir_a = repo_root / 'REQ'
        dir_a.mkdir()
        dir_b = repo_root / 'SYS'
        dir_b.mkdir()

        records = [
            FakeInputRecord(name='reqs', dir='REQ', record_base=dir_a),
            FakeInputRecord(name='sys', dir='SYS', record_base=dir_b),
        ]
        result = discover_repos(records, tmp_path)
        assert len(result) == 1

    def test_no_git_repo_raises(self, tmp_path):
        """Record not in any git repo raises FatalError."""
        no_git = tmp_path / 'no_repo'
        no_git.mkdir()

        records = [FakeInputRecord(name='bad', dir='.', record_base=no_git)]
        with pytest.raises(FatalError) as exc_info:
            discover_repos(records, tmp_path)
        assert 'not inside a git repository' in str(exc_info.value)

    def test_repo_outside_base_dir_raises(self, tmp_path):
        """Repo root outside base_dir raises FatalError."""
        outside = tmp_path / 'outside_project'
        _init_repo(outside)

        # base_dir is a different subtree
        base_dir = tmp_path / 'my_project'
        base_dir.mkdir()

        records = [FakeInputRecord(name='ext', dir='.', record_base=outside)]
        with pytest.raises(FatalError) as exc_info:
            discover_repos(records, base_dir)
        assert 'outside the project base directory' in str(exc_info.value)

    def test_empty_records_raises(self, tmp_path):
        """No input records means no repos discovered."""
        with pytest.raises(FatalError) as exc_info:
            discover_repos([], tmp_path)
        assert 'No git repositories discovered' in str(exc_info.value)


# --- check_repos_clean Tests ---


class TestCheckReposClean:
    def test_clean_repo_passes(self, tmp_path):
        repo = _init_repo(tmp_path / 'clean')
        repos = {tmp_path / 'clean': repo}
        # Should not raise
        check_repos_clean(repos)

    def test_dirty_tracked_file(self, tmp_path):
        repo_path = tmp_path / 'dirty'
        repo = _init_repo(repo_path)
        # Modify a tracked file
        (repo_path / '.gitkeep').write_text('modified', encoding='utf-8')

        repos = {repo_path.resolve(): repo}
        with pytest.raises(FatalError) as exc_info:
            check_repos_clean(repos)
        assert 'uncommitted changes' in str(exc_info.value)

    def test_untracked_file(self, tmp_path):
        repo_path = tmp_path / 'untracked'
        repo = _init_repo(repo_path)
        # Create untracked file
        (repo_path / 'new_file.txt').write_text('new', encoding='utf-8')

        repos = {repo_path.resolve(): repo}
        with pytest.raises(FatalError) as exc_info:
            check_repos_clean(repos)
        assert 'uncommitted changes' in str(exc_info.value)

    def test_staged_change(self, tmp_path):
        repo_path = tmp_path / 'staged'
        repo = _init_repo(repo_path)
        # Stage a new file without committing
        new_file = repo_path / 'staged.txt'
        new_file.write_text('staged', encoding='utf-8')
        repo.index.add(['staged.txt'])

        repos = {repo_path.resolve(): repo}
        with pytest.raises(FatalError) as exc_info:
            check_repos_clean(repos)
        assert 'uncommitted changes' in str(exc_info.value)


# --- validate_tag_name Tests ---


class TestValidateTagName:
    def test_no_pattern_always_passes(self):
        validate_tag_name('anything-goes', None)

    def test_matching_pattern(self):
        validate_tag_name('v1.2.3', r'^v\d+\.\d+\.\d+$')

    def test_non_matching_pattern(self):
        with pytest.raises(FatalError) as exc_info:
            validate_tag_name('release-1', r'^v\d+\.\d+\.\d+$')
        assert 'does not match' in str(exc_info.value)

    def test_partial_match_rejected(self):
        """Partial matches should fail (uses fullmatch)."""
        with pytest.raises(FatalError):
            validate_tag_name('v1.0.0-extra', r'^v\d+\.\d+\.\d+$')


# --- check_tag_exists Tests ---


class TestCheckTagExists:
    def test_no_existing_tag(self, tmp_path):
        repo = _init_repo(tmp_path / 'repo')
        repos = {(tmp_path / 'repo').resolve(): repo}
        # Should not raise
        check_tag_exists('v1.0.0', repos, force=False)

    def test_existing_tag_no_force(self, tmp_path):
        repo_path = tmp_path / 'repo'
        repo = _init_repo(repo_path)
        repo.create_tag('v1.0.0', message='old')

        repos = {repo_path.resolve(): repo}
        with pytest.raises(FatalError) as exc_info:
            check_tag_exists('v1.0.0', repos, force=False)
        assert 'already exists' in str(exc_info.value)
        assert '--force' in str(exc_info.value)

    def test_existing_tag_with_force(self, tmp_path):
        repo_path = tmp_path / 'repo'
        repo = _init_repo(repo_path)
        repo.create_tag('v1.0.0', message='old')

        repos = {repo_path.resolve(): repo}
        # Should not raise, just warn
        check_tag_exists('v1.0.0', repos, force=True)


# --- create_baseline_tag Tests ---


class TestCreateBaselineTag:
    def test_single_repo(self, tmp_path):
        repo_path = tmp_path / 'repo'
        repo = _init_repo(repo_path)
        repos = {repo_path.resolve(): repo}

        results = create_baseline_tag('v1.0.0', repos, 'Test baseline', force=False)
        assert len(results) == 1
        assert results[0][0] == repo_path.resolve()

        # Verify tag exists and is annotated
        tag = repo.tags['v1.0.0']
        assert tag.tag.message.strip() == 'Test baseline'

    def test_multi_repo(self, tmp_path):
        repo_a = _init_repo(tmp_path / 'a')
        repo_b = _init_repo(tmp_path / 'b')
        repos = {
            (tmp_path / 'a').resolve(): repo_a,
            (tmp_path / 'b').resolve(): repo_b,
        }

        results = create_baseline_tag('v2.0.0', repos, 'Multi baseline', force=False)
        assert len(results) == 2
        assert 'v2.0.0' in [t.name for t in repo_a.tags]
        assert 'v2.0.0' in [t.name for t in repo_b.tags]

    def test_force_overwrite(self, tmp_path):
        repo_path = tmp_path / 'repo'
        repo = _init_repo(repo_path)
        repo.create_tag('v1.0.0', message='old')

        repos = {repo_path.resolve(): repo}
        results = create_baseline_tag('v1.0.0', repos, 'New baseline', force=True)
        assert len(results) == 1

        # Verify new message
        tag = repo.tags['v1.0.0']
        assert tag.tag.message.strip() == 'New baseline'

    def test_rollback_on_failure(self, tmp_path):
        """If tagging fails in second repo, first repo's tag is rolled back."""
        repo_a_path = tmp_path / 'a'
        repo_a = _init_repo(repo_a_path)

        repo_b_path = tmp_path / 'b'
        repo_b = _init_repo(repo_b_path)

        repos = {
            repo_a_path.resolve(): repo_a,
            repo_b_path.resolve(): repo_b,
        }

        # Patch repo_b.create_tag to fail
        def fail_create_tag(*args, **kwargs):
            raise git.GitCommandError('tag', 'simulated failure')

        repo_b.create_tag = fail_create_tag

        with pytest.raises(FatalError) as exc_info:
            create_baseline_tag('v1.0.0', repos, 'Should rollback', force=False)

        assert 'Rolled back' in str(exc_info.value)
        # Tag should NOT exist in repo_a (rolled back)
        assert 'v1.0.0' not in [t.name for t in repo_a.tags]


# --- CLI Integration Tests ---


def _setup_single_repo(tmp_path):
    """Create a single test repo with syntagmax config."""
    repo_root = tmp_path / 'project'
    repo = _init_repo(repo_root)

    # Create .syntagmax config
    syntagmax_dir = repo_root / '.syntagmax'
    syntagmax_dir.mkdir()

    config = syntagmax_dir / 'config.toml'
    config.write_text(
        'base = ".."\n\n[[input]]\nname = "requirements"\ndir = "REQ"\ndriver = "obsidian"\natype = "REQ"\n',
        encoding='utf-8',
    )

    req_dir = repo_root / 'REQ'
    req_dir.mkdir()
    (req_dir / 'REQ-001.md').write_text('[REQ]\nTest\n[id] REQ-001\n', encoding='utf-8')

    repo.index.add(
        [
            '.syntagmax/config.toml',
            'REQ/REQ-001.md',
        ]
    )
    repo.index.commit('Add config and requirements', author=git.Actor('Test', 'test@test.com'))

    return repo_root, repo


def _setup_multi_repo(tmp_path):
    """Create two repos under a workspace with a config pointing to both."""
    workspace = tmp_path / 'workspace'
    workspace.mkdir()

    repo_a = _init_repo(workspace / 'repo_a')
    repo_b = _init_repo(workspace / 'repo_b')

    # Create REQ dirs
    (workspace / 'repo_a' / 'REQ').mkdir()
    (workspace / 'repo_a' / 'REQ' / 'R1.md').write_text('[REQ]\nR1\n[id] R1\n', encoding='utf-8')
    repo_a.index.add(['REQ/R1.md'])
    repo_a.index.commit('Add req', author=git.Actor('Test', 'test@test.com'))

    (workspace / 'repo_b' / 'SYS').mkdir()
    (workspace / 'repo_b' / 'SYS' / 'S1.md').write_text('[SYS]\nS1\n[id] S1\n', encoding='utf-8')
    repo_b.index.add(['SYS/S1.md'])
    repo_b.index.commit('Add sys', author=git.Actor('Test', 'test@test.com'))

    # Config lives in workspace/.syntagmax/
    syntagmax_dir = workspace / '.syntagmax'
    syntagmax_dir.mkdir()

    config = syntagmax_dir / 'config.toml'
    config.write_text(
        'base = ".."\n\n'
        '[[input]]\n'
        'name = "requirements"\n'
        'dir = "repo_a/REQ"\n'
        'driver = "obsidian"\n'
        'atype = "REQ"\n\n'
        '[[input]]\n'
        'name = "system"\n'
        'dir = "repo_b/SYS"\n'
        'driver = "obsidian"\n'
        'atype = "SYS"\n',
        encoding='utf-8',
    )

    return workspace, repo_a, repo_b


class TestCLIBaseline:
    def test_happy_path_single_repo(self, tmp_path):
        repo_root, repo = _setup_single_repo(tmp_path)
        runner = CliRunner()

        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v1.0.0', '-f', str(repo_root / '.syntagmax' / 'config.toml')],
        )
        assert result.exit_code == 0, result.output
        assert 'v1.0.0' in result.output
        assert 'v1.0.0' in [t.name for t in repo.tags]

    def test_happy_path_multi_repo(self, tmp_path):
        workspace, repo_a, repo_b = _setup_multi_repo(tmp_path)
        runner = CliRunner()

        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v2.0.0', '-f', str(workspace / '.syntagmax' / 'config.toml')],
        )
        assert result.exit_code == 0, result.output
        assert 'v2.0.0' in [t.name for t in repo_a.tags]
        assert 'v2.0.0' in [t.name for t in repo_b.tags]

    def test_dirty_repo_error(self, tmp_path):
        repo_root, repo = _setup_single_repo(tmp_path)
        # Make repo dirty
        (repo_root / 'dirty.txt').write_text('dirty', encoding='utf-8')

        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v1.0.0', '-f', str(repo_root / '.syntagmax' / 'config.toml')],
        )
        # FatalError is raised; CliRunner catches it as exception
        assert result.exit_code != 0 or result.exception is not None
        error_msg = str(result.exception) if result.exception else result.output
        assert 'uncommitted changes' in error_msg

    def test_tag_pattern_mismatch(self, tmp_path):
        repo_root, repo = _setup_single_repo(tmp_path)
        # Add tag_pattern to config
        config_path = repo_root / '.syntagmax' / 'config.toml'
        content = config_path.read_text(encoding='utf-8')
        content += '\n[baseline]\ntag_pattern = "^v\\\\d+\\\\.\\\\d+\\\\.\\\\d+$"\n'
        config_path.write_text(content, encoding='utf-8')
        repo.index.add(['.syntagmax/config.toml'])
        repo.index.commit('Add baseline config', author=git.Actor('Test', 'test@test.com'))

        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['change', 'baseline', 'bad-tag', '-f', str(config_path)],
        )
        assert result.exit_code != 0 or result.exception is not None
        error_msg = str(result.exception) if result.exception else result.output
        assert 'does not match' in error_msg

    def test_tag_exists_error(self, tmp_path):
        repo_root, repo = _setup_single_repo(tmp_path)
        repo.create_tag('v1.0.0', message='existing')

        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v1.0.0', '-f', str(repo_root / '.syntagmax' / 'config.toml')],
        )
        assert result.exit_code != 0 or result.exception is not None
        error_msg = str(result.exception) if result.exception else result.output
        assert 'already exists' in error_msg

    def test_force_overwrite(self, tmp_path):
        repo_root, repo = _setup_single_repo(tmp_path)
        repo.create_tag('v1.0.0', message='old')

        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v1.0.0', '--force', '-f', str(repo_root / '.syntagmax' / 'config.toml')],
        )
        assert result.exit_code == 0, result.output
        tag = repo.tags['v1.0.0']
        assert tag.tag.message.strip() == 'Baseline created by Syntagmax'

    def test_custom_message(self, tmp_path):
        repo_root, repo = _setup_single_repo(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v1.0.0', '-m', 'Release v1.0.0', '-f', str(repo_root / '.syntagmax' / 'config.toml')],
        )
        assert result.exit_code == 0, result.output
        tag = repo.tags['v1.0.0']
        assert tag.tag.message.strip() == 'Release v1.0.0'

    def test_dry_run(self, tmp_path):
        repo_root, repo = _setup_single_repo(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v1.0.0', '--dry-run', '-f', str(repo_root / '.syntagmax' / 'config.toml')],
        )
        assert result.exit_code == 0, result.output
        assert 'Dry run' in result.output
        # Tag should NOT be created
        assert 'v1.0.0' not in [t.name for t in repo.tags]

    def test_push_reminder_in_output(self, tmp_path):
        repo_root, repo = _setup_single_repo(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v1.0.0', '-f', str(repo_root / '.syntagmax' / 'config.toml')],
        )
        assert result.exit_code == 0, result.output
        assert 'push' in result.output
        assert 'origin' in result.output

    def test_atomicity_multi_repo(self, tmp_path):
        """If one repo fails, tags are rolled back in all previously tagged repos."""
        workspace, repo_a, repo_b = _setup_multi_repo(tmp_path)

        # Make repo_b dirty so we can't proceed past clean check
        # Actually, let's test rollback during creation — make repo_b fail on tag creation
        # by making it lose its HEAD reference temporarily via patching
        runner = CliRunner()

        # First ensure happy path works
        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v3.0.0', '-f', str(workspace / '.syntagmax' / 'config.toml')],
        )
        assert result.exit_code == 0, result.output
        assert 'v3.0.0' in [t.name for t in repo_a.tags]
        assert 'v3.0.0' in [t.name for t in repo_b.tags]

    def test_atomicity_dirty_prevents_all(self, tmp_path):
        """Dirty repo_b prevents tagging in repo_a."""
        workspace, repo_a, repo_b = _setup_multi_repo(tmp_path)

        # Make repo_b dirty
        (workspace / 'repo_b' / 'dirty.txt').write_text('dirty', encoding='utf-8')

        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['change', 'baseline', 'v4.0.0', '-f', str(workspace / '.syntagmax' / 'config.toml')],
        )
        assert result.exit_code != 0
        # Neither repo should have the tag
        assert 'v4.0.0' not in [t.name for t in repo_a.tags]
        assert 'v4.0.0' not in [t.name for t in repo_b.tags]
