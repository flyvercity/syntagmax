# SPDX-License-Identifier: MIT
import pytest
import shutil
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from syntagmax.cli import rms
from syntagmax.cli_publish import _copy_manifest_images, _run_pandoc_conversion
from syntagmax.errors import FatalError
from syntagmax.params import Params
from syntagmax.config import Config


def test_copy_manifest_images_none():
    # Should exit early without errors if manifest is None
    _copy_manifest_images(None, Path("/nonexistent/path"))


def test_copy_manifest_images_clean_stale(tmp_path):
    output_dir = tmp_path / "output"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True)

    # Create stale file
    stale_file = images_dir / "stale.png"
    stale_file.write_text("stale", encoding="utf-8")

    manifest = MagicMock()
    manifest.entries = {}

    _copy_manifest_images(manifest, output_dir)
    assert not stale_file.exists()


def test_copy_manifest_images_copy_and_missing_warnings(tmp_path, caplog):
    output_dir = tmp_path / "output"

    # Existing source
    src_file = tmp_path / "img.png"
    src_file.write_text("data", encoding="utf-8")

    # Non-existing source
    missing_src = tmp_path / "missing.png"

    manifest = MagicMock()
    manifest.entries = {
        src_file: Path("images/img.png"),
        missing_src: Path("images/missing.png"),
    }

    with caplog.at_level(logging.WARNING):
        _copy_manifest_images(manifest, output_dir)

    assert (output_dir / "images/img.png").exists()
    assert (output_dir / "images/img.png").read_text(encoding="utf-8") == "data"
    assert not (output_dir / "images/missing.png").exists()
    assert "Image source file not found, skipping" in caplog.text


@patch("syntagmax.pandoc.convert")
def test_run_pandoc_conversion(mock_convert, tmp_path):
    md_path = tmp_path / "doc.md"

    # Success scenario
    mock_convert.return_value = (True, "success")
    success = _run_pandoc_conversion(md_path, docx=True, pdf=True)
    assert success is True
    assert mock_convert.call_count == 2

    mock_convert.reset_mock()

    # Failure scenario
    mock_convert.return_value = (False, "error")
    success = _run_pandoc_conversion(md_path, docx=True, pdf=False)
    assert success is False
    assert mock_convert.call_count == 1


class TestPublishCLI:
    def test_publish_cli_basic(self, tmp_path):
        # Create default .syntagmax directory
        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()

        # Write config.toml in default location
        cfg = dot_syntagmax / 'config.toml'
        cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

        # Create input dir & file
        sys_dir = tmp_path / 'SYS'
        sys_dir.mkdir()
        f = sys_dir / 'sys.md'
        f.write_text('[< ID=SYS-1 >>> System shall do X. >]', encoding='utf-8')

        # Create default .syntagmax/publish.yaml
        default_yaml = dot_syntagmax / 'publish.yaml'
        default_yaml.write_text(
            'start_level: 2\nrender:\n  SYS:\n    - type: text\n      mode: inline\n      attributes:\n        - contents:\n            alias: "Body"\n',
            encoding='utf-8',
        )

        runner = CliRunner()
        # Publish separately
        out_dir = tmp_path / 'out'
        result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--output', str(out_dir)])
        assert result.exit_code == 0, result.output

        file_path = out_dir / 'rec1.md'
        assert file_path.exists()
        content = file_path.read_text(encoding='utf-8')
        assert '## sys' in content  # file heading: start_level=2, multi_record=False
        assert '**Body**: System shall do X.' in content

        # Run publish consolidated (--single)
        single_file = tmp_path / 'combined.md'
        result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--single', '--output', str(single_file)])
        assert result.exit_code == 0, result.output
        assert single_file.exists()
        content = single_file.read_text(encoding='utf-8')
        assert '## sys' in content  # single record with --all: multi_record=False (only 1 record)
        assert '**Body**: System shall do X.' in content

    def test_publish_date_suffix(self, tmp_path):
        from datetime import datetime

        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg = dot_syntagmax / 'config.toml'
        cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

        sys_dir = tmp_path / 'SYS'
        sys_dir.mkdir()
        f = sys_dir / 'sys.md'
        f.write_text('[< ID=SYS-1 >>> System shall do X. >]', encoding='utf-8')

        runner = CliRunner()
        out_dir = tmp_path / 'out'

        # Publish with --date-suffix
        result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--date-suffix', '--output', str(out_dir)])
        assert result.exit_code == 0, result.output

        date_str = datetime.now().strftime('%Y-%m-%d')
        expected_file = out_dir / f'rec1_{date_str}.md'
        assert expected_file.exists(), f'Expected {expected_file} to exist, found: {list(out_dir.iterdir())}'

        # Verify content
        content = expected_file.read_text(encoding='utf-8')
        assert 'SYS-1' in content

    def test_publish_date_suffix_incompatible_with_single(self, tmp_path):
        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg = dot_syntagmax / 'config.toml'
        cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

        sys_dir = tmp_path / 'SYS'
        sys_dir.mkdir()
        f = sys_dir / 'sys.md'
        f.write_text('[< ID=SYS-1 >>> X >]', encoding='utf-8')

        runner = CliRunner()
        result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--single', '--date-suffix'])
        assert result.exit_code != 0


def test_publish_missing_records_and_not_all(tmp_path):
    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish'])
    assert result.exit_code != 0
    assert "Either RECORD names or --all must be specified" in result.output


def test_publish_config_file_not_found(tmp_path):
    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '-f', 'missing.toml'])
    assert result.exit_code != 0
    assert "Configuration file" in result.output
    assert "does not exist" in result.output


def test_publish_record_not_found(tmp_path):
    dot_syntagmax = tmp_path / '.syntagmax'
    dot_syntagmax.mkdir()
    cfg = dot_syntagmax / 'config.toml'
    cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', 'nonexistent_record'])
    assert result.exit_code != 0
    assert 'Input record "nonexistent_record" not found in config' in result.output


@patch("syntagmax.pandoc.check_pandoc", return_value=False)
def test_publish_pandoc_not_found_warning(mock_check, tmp_path):
    dot_syntagmax = tmp_path / '.syntagmax'
    dot_syntagmax.mkdir()
    cfg = dot_syntagmax / 'config.toml'
    cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

    sys_dir = tmp_path / 'SYS'
    sys_dir.mkdir()
    f = sys_dir / 'sys.md'
    f.write_text('[< ID=SYS-1 >>> X >]', encoding='utf-8')

    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--docx'])
    assert result.exit_code == 0
    assert "Warning: pandoc not found in PATH" in result.output


def test_publish_invalid_record_name(tmp_path):
    dot_syntagmax = tmp_path / '.syntagmax'
    dot_syntagmax.mkdir()
    cfg = dot_syntagmax / 'config.toml'
    # Use '.' as name, which will cause safe_record_name to resolve to '.'
    cfg.write_text('base = ".."\n[[input]]\nname="."\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

    sys_dir = tmp_path / 'SYS'
    sys_dir.mkdir()
    f = sys_dir / 'sys.md'
    f.write_text('[< ID=SYS-1 >>> X >]', encoding='utf-8')

    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all'])
    assert result.exit_code != 0
    assert 'Invalid record name for output filename' in result.output


@patch("syntagmax.pandoc.convert", return_value=(True, "success"))
@patch("syntagmax.pandoc.check_pandoc", return_value=True)
def test_publish_docx_template_none(mock_check, mock_convert, tmp_path):
    dot_syntagmax = tmp_path / '.syntagmax'
    dot_syntagmax.mkdir()
    cfg = dot_syntagmax / 'config.toml'
    cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

    sys_dir = tmp_path / 'SYS'
    sys_dir.mkdir()
    f = sys_dir / 'sys.md'
    f.write_text('[< ID=SYS-1 >>> X >]', encoding='utf-8')

    runner = CliRunner()
    # Should work without FatalError since docx_template=none is resolved to None
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--docx', '--docx-template', 'none'])
    assert result.exit_code == 0


@patch("syntagmax.pandoc.check_pandoc", return_value=True)
def test_publish_docx_template_missing_raises_fatal(mock_check, tmp_path):
    dot_syntagmax = tmp_path / '.syntagmax'
    dot_syntagmax.mkdir()
    cfg = dot_syntagmax / 'config.toml'
    cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

    sys_dir = tmp_path / 'SYS'
    sys_dir.mkdir()
    f = sys_dir / 'sys.md'
    f.write_text('[< ID=SYS-1 >>> X >]', encoding='utf-8')

    runner = CliRunner()
    result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--docx', '--docx-template', 'nonexistent.docx'])
    assert result.exit_code != 0
    assert result.exception is not None
    assert "DOCX template not found" in str(result.exception)
