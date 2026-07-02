# SPDX-License-Identifier: MIT
import subprocess
from unittest.mock import MagicMock, patch

import pytest


class TestCheckPandoc:
    def test_pandoc_available(self):
        from syntagmax.pandoc import check_pandoc

        with patch('syntagmax.pandoc.shutil.which', return_value='/usr/bin/pandoc'):
            assert check_pandoc() is True

    def test_pandoc_not_available(self):
        from syntagmax.pandoc import check_pandoc

        with patch('syntagmax.pandoc.shutil.which', return_value=None):
            assert check_pandoc() is False


class TestConvert:
    def test_successful_conversion(self, tmp_path):
        from syntagmax.pandoc import convert

        source = tmp_path / 'test.md'
        source.write_text('# Hello\n\nWorld\n', encoding='utf-8')
        output = tmp_path / 'test.docx'

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ''

        with patch('syntagmax.pandoc.subprocess.run', return_value=mock_result) as mock_run:
            success, message = convert(source, output, 'docx')

        assert success is True
        assert 'Successfully converted to docx' in message
        mock_run.assert_called_once_with(
            ['pandoc', str(source), '-o', str(output)],
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_failed_conversion_nonzero_exit(self, tmp_path):
        from syntagmax.pandoc import convert

        source = tmp_path / 'test.md'
        source.write_text('# Hello\n', encoding='utf-8')
        output = tmp_path / 'test.pdf'

        mock_result = MagicMock()
        mock_result.returncode = 43
        mock_result.stderr = 'pdflatex not found'

        with patch('syntagmax.pandoc.subprocess.run', return_value=mock_result):
            success, message = convert(source, output, 'pdf')

        assert success is False
        assert '43' in message
        assert 'pdflatex not found' in message

    def test_pandoc_not_found_at_runtime(self, tmp_path):
        from syntagmax.pandoc import convert

        source = tmp_path / 'test.md'
        source.write_text('# Hello\n', encoding='utf-8')
        output = tmp_path / 'test.docx'

        with patch('syntagmax.pandoc.subprocess.run', side_effect=FileNotFoundError):
            success, message = convert(source, output, 'docx')

        assert success is False
        assert 'not found' in message

    def test_pandoc_timeout(self, tmp_path):
        from syntagmax.pandoc import convert

        source = tmp_path / 'test.md'
        source.write_text('# Hello\n', encoding='utf-8')
        output = tmp_path / 'test.docx'

        with patch('syntagmax.pandoc.subprocess.run', side_effect=subprocess.TimeoutExpired(cmd='pandoc', timeout=120)):
            success, message = convert(source, output, 'docx')

        assert success is False
        assert 'timed out' in message

    def test_stderr_truncation(self, tmp_path):
        from syntagmax.pandoc import convert

        source = tmp_path / 'test.md'
        source.write_text('# Hello\n', encoding='utf-8')
        output = tmp_path / 'test.pdf'

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = 'x' * 1000

        with patch('syntagmax.pandoc.subprocess.run', return_value=mock_result):
            success, message = convert(source, output, 'pdf')

        assert success is False
        # Stderr should be truncated to 500 chars + '...'
        assert '...' in message
        assert len(message) < 600


class TestPublishCLIWithPandoc:
    @pytest.fixture
    def project_dir(self, tmp_path):
        """Set up a minimal project directory for CLI tests."""
        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg = dot_syntagmax / 'config.toml'
        cfg.write_text(
            'base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n',
            encoding='utf-8',
        )

        sys_dir = tmp_path / 'SYS'
        sys_dir.mkdir()
        f = sys_dir / 'sys.md'
        f.write_text('[< ID=SYS-1 >>> System shall do X. >]', encoding='utf-8')

        return tmp_path

    def test_docx_flag_calls_pandoc(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        runner = CliRunner()
        out_dir = project_dir / 'out'

        with patch('syntagmax.pandoc.check_pandoc', return_value=True) as mock_check, \
             patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
            result = runner.invoke(rms, ['--cwd', str(project_dir), 'publish', '--all', '--docx', '--output', str(out_dir)])

        assert result.exit_code == 0, result.output
        # Markdown file should exist
        md_file = out_dir / 'rec1.md'
        assert md_file.exists()
        # Pandoc check should have been called
        mock_check.assert_called_once()
        # Convert should have been called with .docx output
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args
        assert str(call_args[0][1]).endswith('.docx')
        assert call_args[0][2] == 'docx'

    def test_pdf_flag_calls_pandoc(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        runner = CliRunner()
        out_dir = project_dir / 'out'

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), \
             patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
            result = runner.invoke(rms, ['--cwd', str(project_dir), 'publish', '--all', '--pdf', '--output', str(out_dir)])

        assert result.exit_code == 0, result.output
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args
        assert str(call_args[0][1]).endswith('.pdf')
        assert call_args[0][2] == 'pdf'

    def test_both_flags_call_pandoc_twice(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        runner = CliRunner()
        out_dir = project_dir / 'out'

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), \
             patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
            result = runner.invoke(rms, ['--cwd', str(project_dir), 'publish', '--all', '--docx', '--pdf', '--output', str(out_dir)])

        assert result.exit_code == 0, result.output
        assert mock_convert.call_count == 2
        formats_called = {call[0][2] for call in mock_convert.call_args_list}
        assert formats_called == {'docx', 'pdf'}

    def test_pandoc_not_found_exits_cleanly(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        runner = CliRunner()
        out_dir = project_dir / 'out'

        with patch('syntagmax.pandoc.check_pandoc', return_value=False), \
             patch('syntagmax.pandoc.convert') as mock_convert:
            result = runner.invoke(rms, ['--cwd', str(project_dir), 'publish', '--all', '--docx', '--output', str(out_dir)])

        assert result.exit_code == 0, result.output
        # Markdown should still be produced
        md_file = out_dir / 'rec1.md'
        assert md_file.exists()
        # Convert should never be called
        mock_convert.assert_not_called()
        # Warning should be visible
        assert 'pandoc not found' in result.output.lower() or 'not found' in result.output.lower()

    def test_pandoc_conversion_failure_exits_cleanly(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        runner = CliRunner()
        out_dir = project_dir / 'out'

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), \
             patch('syntagmax.pandoc.convert', return_value=(False, 'pandoc exited with status 1: some error')):
            result = runner.invoke(rms, ['--cwd', str(project_dir), 'publish', '--all', '--docx', '--output', str(out_dir)])

        assert result.exit_code == 0, result.output
        # Markdown should still be produced
        md_file = out_dir / 'rec1.md'
        assert md_file.exists()
        # Warning about failure should be in output
        assert 'failed' in result.output.lower()

    def test_single_mode_with_docx(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        runner = CliRunner()
        out_file = project_dir / 'out' / 'combined.md'

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), \
             patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
            result = runner.invoke(rms, ['--cwd', str(project_dir), 'publish', '--all', '--single', '--docx', '--output', str(out_file)])

        assert result.exit_code == 0, result.output
        assert out_file.exists()
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args
        expected_docx = out_file.with_suffix('.docx')
        assert call_args[0][1] == expected_docx
