# SPDX-License-Identifier: MIT
from pathlib import Path
from click.testing import CliRunner
from syntagmax.cli import rms


def test_ci_install_analyze_github(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'ci', '--target', 'github', 'install', 'analyze'])
    assert result.exit_code == 0, result.output
    assert 'GitHub workflow created at' in result.output

    expected_file = tmp_path / '.github' / 'workflows' / 'syntagmax-analyze.yml'
    assert expected_file.exists()
    content = expected_file.read_text(encoding='utf-8')
    assert 'name: Syntagmax Analyze' in content
    assert 'syntagmax analyze' in content
    assert '.syntagmax/reports/report.md' in content


def test_ci_install_analyze_github_default(tmp_path: Path):
    # Target should default to github
    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'ci', 'install', 'analyze'])
    assert result.exit_code == 0, result.output
    assert 'GitHub workflow created at' in result.output

    expected_file = tmp_path / '.github' / 'workflows' / 'syntagmax-analyze.yml'
    assert expected_file.exists()


def test_ci_install_analyze_gitlab(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'ci', '--target', 'gitlab', 'install', 'analyze'])
    assert result.exit_code == 0, result.output
    assert 'GitLab CI configuration created at' in result.output

    expected_file = tmp_path / '.gitlab-ci.yml'
    assert expected_file.exists()
    content = expected_file.read_text(encoding='utf-8')
    assert 'syntagmax-analyze:' in content
    assert 'syntagmax analyze' in content
    assert '.syntagmax/reports/report.md' in content


def test_ci_install_publish_github(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'ci', '--target', 'github', 'install', 'publish'])
    assert result.exit_code == 0, result.output
    assert 'GitHub workflow created at' in result.output

    expected_file = tmp_path / '.github' / 'workflows' / 'syntagmax-publish.yml'
    assert expected_file.exists()
    content = expected_file.read_text(encoding='utf-8')
    assert 'name: Syntagmax Publish' in content
    assert 'syntagmax publish --all --single' in content
    assert '.syntagmax/reports/published.md' in content


def test_ci_install_publish_gitlab(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'ci', '--target', 'gitlab', 'install', 'publish'])
    assert result.exit_code == 0, result.output
    assert 'GitLab CI configuration created at' in result.output

    expected_file = tmp_path / '.gitlab-ci.yml'
    assert expected_file.exists()
    content = expected_file.read_text(encoding='utf-8')
    assert 'syntagmax-publish:' in content
    assert 'syntagmax publish --all --single' in content
    assert '.syntagmax/reports/published.md' in content


def test_ci_install_respects_cwd_omitted(tmp_path: Path, monkeypatch):
    # If no --cwd option is supplied, files should be created in current directory
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(rms, ['ci', 'install', 'analyze'])
    assert result.exit_code == 0, result.output
    expected_file = tmp_path / '.github' / 'workflows' / 'syntagmax-analyze.yml'
    assert expected_file.exists()
