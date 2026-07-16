# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-07-15
# Description: Integration tests for the change report command.

import pytest
import git
from click.testing import CliRunner
from syntagmax.cli import rms


def _setup_test_repo(tmp_path):
    """Create a test git repo with syntagmax config and sample artifacts."""
    # Init git repo
    repo = git.Repo.init(tmp_path)

    # Create .syntagmax config
    syntagmax_dir = tmp_path / '.syntagmax'
    syntagmax_dir.mkdir()

    # Add .gitignore for worktrees
    gitignore = tmp_path / '.gitignore'
    gitignore.write_text('.syntagmax/worktrees/\n', encoding='utf-8')

    config = syntagmax_dir / 'config.toml'
    config.write_text("""
base = ".."

[[input]]
name = "requirements"
dir = "REQ"
driver = "obsidian"
atype = "REQ"
marker = "REQ"

[metamodel]
filename = "project.syntagmax"
""", encoding='utf-8')

    # Create metamodel
    metamodel = syntagmax_dir / 'project.syntagmax'
    metamodel.write_text("""
artifact REQ:
    id is string
    attribute contents is mandatory string
    attribute status is mandatory enum [draft, active, retired]
    attribute priority is mandatory enum [low, medium, high, critical]
""", encoding='utf-8')

    # Create REQ directory with sample artifacts
    req_dir = tmp_path / 'REQ'
    req_dir.mkdir()

    req1 = req_dir / 'REQ-001.md'
    req1.write_text("""[REQ]
The system shall do something.
[id] REQ-001
```yaml
attrs:
  status: draft
  priority: high
```
""", encoding='utf-8')

    req2 = req_dir / 'REQ-002.md'
    req2.write_text("""[REQ]
The system shall do something else.
[id] REQ-002
```yaml
attrs:
  status: draft
  priority: medium
```
""", encoding='utf-8')

    # First commit
    repo.index.add(['.gitignore', '.syntagmax/config.toml', '.syntagmax/project.syntagmax',
                    'REQ/REQ-001.md', 'REQ/REQ-002.md'])
    repo.index.commit('Initial commit', author=git.Actor('Test', 'test@test.com'))

    # Make changes
    # Modify REQ-001 (change status and content)
    req1.write_text("""[REQ]
The system shall do something important.
[id] REQ-001
```yaml
attrs:
  status: active
  priority: critical
```
""", encoding='utf-8')

    # Add new REQ-003
    req3 = req_dir / 'REQ-003.md'
    req3.write_text("""[REQ]
The system shall have a new feature.
[id] REQ-003
```yaml
attrs:
  status: draft
  priority: low
```
""", encoding='utf-8')

    # Remove REQ-002
    req2.unlink()

    # Second commit
    repo.index.add(['REQ/REQ-001.md', 'REQ/REQ-003.md'])
    repo.index.remove(['REQ/REQ-002.md'])
    repo.index.commit('Update requirements', author=git.Actor('Test', 'test@test.com'))

    return repo, tmp_path


@pytest.fixture
def change_report_repo(tmp_path):
    return _setup_test_repo(tmp_path)


def test_basic_change_report(change_report_repo):
    """Test that a basic change report is generated successfully."""
    repo, repo_path = change_report_repo
    runner = CliRunner()
    result = runner.invoke(rms, [
        '--cwd', str(repo_path),
        'change', 'report',
        '--base', 'HEAD~1',
        '--target', 'HEAD',
    ])
    assert result.exit_code == 0, f'CLI failed: {result.output}'
    # Check report file was created
    report_dir = repo_path / '.syntagmax' / 'reports' / 'change'
    assert report_dir.exists()
    reports = list(report_dir.glob('*.md'))
    assert len(reports) >= 1


def test_report_contains_all_sections(change_report_repo):
    """Test that the report contains all required sections."""
    repo, repo_path = change_report_repo
    runner = CliRunner()
    result = runner.invoke(rms, [
        '--cwd', str(repo_path),
        'change', 'report',
        '--base', 'HEAD~1',
        '--target', 'HEAD',
        '--output', 'console',
    ])
    assert result.exit_code == 0
    output = result.output
    assert '# Change Report' in output
    assert '## Repository Information' in output
    assert '## Summary' in output
    assert '## Changed Files' in output
    assert '## Detailed Changes' in output


def test_summary_statistics(change_report_repo):
    """Test that summary statistics are accurate."""
    repo, repo_path = change_report_repo
    runner = CliRunner()
    result = runner.invoke(rms, [
        '--cwd', str(repo_path),
        'change', 'report',
        '--base', 'HEAD~1',
        '--target', 'HEAD',
        '--output', 'console',
    ])
    assert result.exit_code == 0
    output = result.output
    # 1 modified (REQ-001), 1 added (REQ-003), 1 removed (REQ-002)
    assert '| Artifacts added | 1 |' in output
    assert '| Artifacts modified | 1 |' in output
    assert '| Artifacts removed | 1 |' in output


def test_output_console(change_report_repo):
    """Test --output console prints to stdout."""
    repo, repo_path = change_report_repo
    runner = CliRunner()
    result = runner.invoke(rms, [
        '--cwd', str(repo_path),
        'change', 'report',
        '--base', 'HEAD~1',
        '--target', 'HEAD',
        '--output', 'console',
    ])
    assert result.exit_code == 0
    assert '# Change Report' in result.output


def test_artifact_changes_detected(change_report_repo):
    """Test that artifact changes are correctly identified."""
    repo, repo_path = change_report_repo
    runner = CliRunner()
    result = runner.invoke(rms, [
        '--cwd', str(repo_path),
        'change', 'report',
        '--base', 'HEAD~1',
        '--target', 'HEAD',
        '--output', 'console',
    ])
    assert result.exit_code == 0
    output = result.output
    # Modified artifact
    assert 'REQ REQ-001 (Modified)' in output
    # Added artifact
    assert 'REQ REQ-003 (Added)' in output
    # Removed artifact
    assert 'REQ REQ-002 (Removed)' in output


def test_filename_format(change_report_repo):
    """Test the report filename follows the naming convention."""
    repo, repo_path = change_report_repo
    runner = CliRunner()
    result = runner.invoke(rms, [
        '--cwd', str(repo_path),
        'change', 'report',
        '--base', 'HEAD~1',
        '--target', 'HEAD',
    ])
    assert result.exit_code == 0
    report_dir = repo_path / '.syntagmax' / 'reports' / 'change'
    reports = list(report_dir.glob('requirements-*-to-*-*.md'))
    assert len(reports) == 1, f'Expected 1 report, got: {reports}'


def test_invalid_revision(tmp_path):
    """Test that invalid revision produces clear error."""
    repo = git.Repo.init(tmp_path)
    gitignore = tmp_path / '.gitignore'
    gitignore.write_text('.syntagmax/worktrees/\n', encoding='utf-8')
    syntagmax_dir = tmp_path / '.syntagmax'
    syntagmax_dir.mkdir()
    config = syntagmax_dir / 'config.toml'
    config.write_text('base = ".."\n[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\n', encoding='utf-8')
    # Need at least one commit for the repo to be valid
    repo.index.add(['.gitignore', '.syntagmax/config.toml'])
    repo.index.commit('init', author=git.Actor('Test', 'test@test.com'))

    runner = CliRunner()
    result = runner.invoke(rms, [
        '--cwd', str(tmp_path),
        'change', 'report',
        '--base', 'nonexistent-rev',
        '--target', 'HEAD',
    ])
    assert result.exit_code != 0


def test_no_changes(change_report_repo):
    """Test that same revision comparison reports no changes."""
    repo, repo_path = change_report_repo
    runner = CliRunner()
    result = runner.invoke(rms, [
        '--cwd', str(repo_path),
        'change', 'report',
        '--base', 'HEAD',
        '--target', 'HEAD',
    ])
    assert result.exit_code == 0
    assert 'No changes' in result.output or 'same revision' in result.output.lower()
