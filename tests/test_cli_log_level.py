# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-07-27
# Description: Integration tests for the --log level CLI option and warnings-as-errors.

from pathlib import Path

from click.testing import CliRunner

from syntagmax.cli import rms


def _make_project(tmp_path: Path, config_extra: str = '', has_metamodel: bool = True) -> Path:
    """Create a minimal project that can run `analyze extract`.

    When has_metamodel=False, no metamodel file is created, triggering
    the 'No static validation model' warning during config loading.
    """
    syntagmax_dir = tmp_path / '.syntagmax'
    syntagmax_dir.mkdir()

    metamodel_line = 'filename = "project.syntagmax"' if has_metamodel else ''

    config_content = f"""\
base = ".."
{config_extra}

[[input]]
name = "reqs"
dir = "reqs"
driver = "obsidian"

[metamodel]
{metamodel_line}
"""
    (syntagmax_dir / 'config.toml').write_text(config_content, encoding='utf-8')

    if has_metamodel:
        mm = syntagmax_dir / 'project.syntagmax'
        mm.write_text('artifact REQ:\n    id is string\n    attribute contents is mandatory string\n', encoding='utf-8')

    # Create minimal input directory
    reqs_dir = tmp_path / 'reqs'
    reqs_dir.mkdir()
    (reqs_dir / 'sample.md').write_text('# Sample\n', encoding='utf-8')

    return tmp_path


def _isolated_env(tmp_path: Path) -> dict[str, str]:
    """Return env dict that isolates SYNTAGMAX_HOME to a non-existent dir."""
    fake_home = str(tmp_path / '_fake_syntagmax_home')
    return {'SYNTAGMAX_HOME': fake_home}


class TestDefaultLogLevel:
    """Test 1: Default log level is info (no --log, no config setting)."""

    def test_default_log_level_info(self, tmp_path: Path):
        project = _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['--cwd', str(project), '-f', '.syntagmax/config.toml', 'analyze', 'extract'],
            env=_isolated_env(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # info messages should appear (e.g. 'Using configuration file')
        assert 'Using configuration file' in result.output


class TestConfigLogLevel:
    """Test 2: Project config `log_level = "error"` respected."""

    def test_config_log_level_error_suppresses_info(self, tmp_path: Path):
        project = _make_project(tmp_path, config_extra='log_level = "error"')
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['--cwd', str(project), '-f', '.syntagmax/config.toml', 'analyze', 'extract'],
            env=_isolated_env(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # With error level, post-resolution info messages should NOT appear.
        # 'Executing step' is logged after config is fully resolved.
        assert 'Executing step' not in result.output


class TestCLIOverridesConfig:
    """Test 3: CLI `--log warning` overrides project config `log_level = "debug"`."""

    def test_cli_log_overrides_config(self, tmp_path: Path):
        project = _make_project(tmp_path, config_extra='log_level = "debug"')
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['--log', 'warning', '--cwd', str(project), '-f', '.syntagmax/config.toml', 'analyze', 'extract'],
            env=_isolated_env(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # With warning level via CLI, debug messages should not appear
        assert 'Configuration file contents' not in result.output
        # And info messages should also not appear
        assert 'Using configuration file' not in result.output


class TestSilentMode:
    """Test 4: `--log silent` suppresses all console log output."""

    def test_silent_suppresses_all_output(self, tmp_path: Path):
        project = _make_project(tmp_path, has_metamodel=False)
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['--log', 'silent', '--cwd', str(project), '-f', '.syntagmax/config.toml', 'analyze', 'extract'],
            env=_isolated_env(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # Silent mode: no log messages at all
        assert 'Using configuration file' not in result.output
        assert 'No static validation model' not in result.output


class TestWarningsAsErrorsConfig:
    """Test 5: `warnings_as_errors = true` in config causes exit code 1 on warnings."""

    def test_config_warnings_as_errors(self, tmp_path: Path):
        project = _make_project(
            tmp_path,
            config_extra='warnings_as_errors = true',
            has_metamodel=False,  # triggers 'No static validation model' warning
        )
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['--cwd', str(project), '-f', '.syntagmax/config.toml', 'analyze', 'extract'],
            env=_isolated_env(tmp_path),
        )
        # Should fail due to warnings treated as errors
        assert result.exit_code != 0 or result.exception is not None


class TestWarningsAsErrorsCLI:
    """Test 6: `--warnings-as-errors` CLI flag works."""

    def test_cli_warnings_as_errors(self, tmp_path: Path):
        project = _make_project(
            tmp_path,
            has_metamodel=False,  # triggers warning
        )
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['--warnings-as-errors', '--cwd', str(project), '-f', '.syntagmax/config.toml', 'analyze', 'extract'],
            env=_isolated_env(tmp_path),
        )
        # Should fail due to warnings treated as errors
        assert result.exit_code != 0 or result.exception is not None


class TestSilentWithWarningsAsErrors:
    """Test 7: `--log silent --warnings-as-errors` → no output, exits non-zero on warnings."""

    def test_silent_wae_no_output_nonzero(self, tmp_path: Path):
        project = _make_project(
            tmp_path,
            has_metamodel=False,  # triggers warning
        )
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['--log', 'silent', '--warnings-as-errors', '--cwd', str(project),
             '-f', '.syntagmax/config.toml', 'analyze', 'extract'],
            env=_isolated_env(tmp_path),
        )
        # Should exit non-zero
        assert result.exit_code != 0 or result.exception is not None
        # No log messages should be visible in output
        assert 'No static validation model' not in result.output


class TestDebugLevel:
    """Test 8: `--log debug` shows debug-level messages."""

    def test_debug_shows_debug_messages(self, tmp_path: Path):
        project = _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['--log', 'debug', '--cwd', str(project), '-f', '.syntagmax/config.toml', 'analyze', 'extract'],
            env=_isolated_env(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # Debug messages should include config dump (may be line-wrapped by RichHandler)
        assert 'DEBUG' in result.output
        assert 'Configuration file' in result.output


class TestNoWarningsAsErrorsOverride:
    """Test 9: `--no-warnings-as-errors` CLI overrides config `true`."""

    def test_no_wae_overrides_config(self, tmp_path: Path):
        project = _make_project(
            tmp_path,
            config_extra='warnings_as_errors = true',
            has_metamodel=False,  # triggers warning
        )
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['--no-warnings-as-errors', '--cwd', str(project),
             '-f', '.syntagmax/config.toml', 'analyze', 'extract'],
            env=_isolated_env(tmp_path),
            catch_exceptions=False,
        )
        # Should succeed because --no-warnings-as-errors overrides config
        assert result.exit_code == 0, result.output
