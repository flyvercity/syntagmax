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

        with (
            patch('syntagmax.pandoc.check_pandoc', return_value=True) as mock_check,
            patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert,
        ):
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

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
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

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
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

        with patch('syntagmax.pandoc.check_pandoc', return_value=False), patch('syntagmax.pandoc.convert') as mock_convert:
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

        with (
            patch('syntagmax.pandoc.check_pandoc', return_value=True),
            patch('syntagmax.pandoc.convert', return_value=(False, 'pandoc exited with status 1: some error')),
        ):
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

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
            result = runner.invoke(rms, ['--cwd', str(project_dir), 'publish', '--all', '--single', '--docx', '--output', str(out_file)])

        assert result.exit_code == 0, result.output
        assert out_file.exists()
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args
        expected_docx = out_file.with_suffix('.docx')
        assert call_args[0][1] == expected_docx


class TestConvertWithReferenceDoc:
    def test_reference_doc_included_for_docx(self, tmp_path):
        from syntagmax.pandoc import convert

        source = tmp_path / 'test.md'
        source.write_text('# Hello\n', encoding='utf-8')
        output = tmp_path / 'test.docx'
        ref_doc = tmp_path / 'template.dotm'
        ref_doc.write_text('fake template', encoding='utf-8')

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ''

        with patch('syntagmax.pandoc.subprocess.run', return_value=mock_result) as mock_run:
            success, message = convert(source, output, 'docx', reference_doc=ref_doc)

        assert success is True
        cmd = mock_run.call_args[0][0]
        assert '--reference-doc' in cmd
        assert str(ref_doc) in cmd

    def test_reference_doc_none_not_included(self, tmp_path):
        from syntagmax.pandoc import convert

        source = tmp_path / 'test.md'
        source.write_text('# Hello\n', encoding='utf-8')
        output = tmp_path / 'test.docx'

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ''

        with patch('syntagmax.pandoc.subprocess.run', return_value=mock_result) as mock_run:
            success, message = convert(source, output, 'docx', reference_doc=None)

        assert success is True
        cmd = mock_run.call_args[0][0]
        assert '--reference-doc' not in cmd

    def test_reference_doc_not_included_for_pdf(self, tmp_path):
        from syntagmax.pandoc import convert

        source = tmp_path / 'test.md'
        source.write_text('# Hello\n', encoding='utf-8')
        output = tmp_path / 'test.pdf'
        ref_doc = tmp_path / 'template.dotm'
        ref_doc.write_text('fake template', encoding='utf-8')

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ''

        with patch('syntagmax.pandoc.subprocess.run', return_value=mock_result) as mock_run:
            success, message = convert(source, output, 'pdf', reference_doc=ref_doc)

        assert success is True
        cmd = mock_run.call_args[0][0]
        assert '--reference-doc' not in cmd


class TestResolveDocxTemplate:
    def test_absent_docx_template_returns_bundled(self, tmp_path):
        from syntagmax.pandoc import resolve_docx_template, BUNDLED_TEMPLATE
        from syntagmax.publish_config import PublishConfig

        pub_config = PublishConfig()
        result = resolve_docx_template(pub_config, 'any-record', tmp_path)
        assert result == BUNDLED_TEMPLATE

    def test_default_template_resolves_relative(self, tmp_path):
        from syntagmax.pandoc import resolve_docx_template
        from syntagmax.publish_config import PublishConfig

        # Create the template file
        templates_dir = tmp_path / 'templates'
        templates_dir.mkdir()
        template_file = templates_dir / 'corp.dotm'
        template_file.write_text('fake', encoding='utf-8')

        pub_config = PublishConfig.model_validate(
            {
                'docx-template': {'default-template': 'templates/corp.dotm'},
            }
        )
        result = resolve_docx_template(pub_config, 'my-record', tmp_path)
        assert result == template_file

    def test_per_record_override(self, tmp_path):
        from syntagmax.pandoc import resolve_docx_template
        from syntagmax.publish_config import PublishConfig

        # Create override template
        override_file = tmp_path / 'override.dotm'
        override_file.write_text('fake', encoding='utf-8')

        # Create default template too
        default_file = tmp_path / 'default.dotm'
        default_file.write_text('fake', encoding='utf-8')

        pub_config = PublishConfig.model_validate(
            {
                'docx-template': {
                    'default-template': 'default.dotm',
                    'overrides': {'my-record': 'override.dotm'},
                },
            }
        )
        result = resolve_docx_template(pub_config, 'my-record', tmp_path)
        assert result == override_file

    def test_none_override_returns_none(self, tmp_path):
        from syntagmax.pandoc import resolve_docx_template
        from syntagmax.publish_config import PublishConfig

        pub_config = PublishConfig.model_validate(
            {
                'docx-template': {
                    'default-template': 'something.dotm',
                    'overrides': {'my-record': 'none'},
                },
            }
        )
        result = resolve_docx_template(pub_config, 'my-record', tmp_path)
        assert result is None

    def test_none_default_returns_none(self, tmp_path):
        from syntagmax.pandoc import resolve_docx_template
        from syntagmax.publish_config import PublishConfig

        pub_config = PublishConfig.model_validate(
            {
                'docx-template': {'default-template': 'none'},
            }
        )
        result = resolve_docx_template(pub_config, 'my-record', tmp_path)
        assert result is None

    def test_missing_custom_path_raises_fatal_error(self, tmp_path):
        from syntagmax.pandoc import resolve_docx_template
        from syntagmax.publish_config import PublishConfig
        from syntagmax.errors import FatalError

        pub_config = PublishConfig.model_validate(
            {
                'docx-template': {'default-template': 'nonexistent.dotm'},
            }
        )
        with pytest.raises(FatalError):
            resolve_docx_template(pub_config, 'my-record', tmp_path)

    def test_missing_override_path_raises_fatal_error(self, tmp_path):
        from syntagmax.pandoc import resolve_docx_template
        from syntagmax.publish_config import PublishConfig
        from syntagmax.errors import FatalError

        pub_config = PublishConfig.model_validate(
            {
                'docx-template': {
                    'overrides': {'my-record': 'missing.dotm'},
                },
            }
        )
        with pytest.raises(FatalError):
            resolve_docx_template(pub_config, 'my-record', tmp_path)

    def test_empty_docx_template_section_returns_bundled(self, tmp_path):
        from syntagmax.pandoc import resolve_docx_template, BUNDLED_TEMPLATE
        from syntagmax.publish_config import PublishConfig

        pub_config = PublishConfig.model_validate(
            {
                'docx-template': {},
            }
        )
        result = resolve_docx_template(pub_config, 'any-record', tmp_path)
        assert result == BUNDLED_TEMPLATE

    def test_non_matching_override_falls_to_default(self, tmp_path):
        from syntagmax.pandoc import resolve_docx_template
        from syntagmax.publish_config import PublishConfig

        # Create default template
        default_file = tmp_path / 'default.dotm'
        default_file.write_text('fake', encoding='utf-8')

        pub_config = PublishConfig.model_validate(
            {
                'docx-template': {
                    'default-template': 'default.dotm',
                    'overrides': {'other-record': 'none'},
                },
            }
        )
        result = resolve_docx_template(pub_config, 'my-record', tmp_path)
        assert result == default_file

    def test_bundled_template_exists(self):
        from syntagmax.pandoc import BUNDLED_TEMPLATE

        assert BUNDLED_TEMPLATE.exists()


class TestPublishCLIWithDocxTemplate:
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

    def test_docx_uses_bundled_template_by_default(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms
        from syntagmax.pandoc import BUNDLED_TEMPLATE

        runner = CliRunner()
        out_dir = project_dir / 'out'

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
            result = runner.invoke(rms, ['--cwd', str(project_dir), 'publish', '--all', '--docx', '--output', str(out_dir)])

        assert result.exit_code == 0, result.output
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args
        assert call_args.kwargs.get('reference_doc') == BUNDLED_TEMPLATE or call_args[1].get('reference_doc') == BUNDLED_TEMPLATE

    def test_docx_template_cli_override(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        runner = CliRunner()
        out_dir = project_dir / 'out'

        # Create a custom template
        custom_template = project_dir / 'custom.dotm'
        custom_template.write_text('fake template', encoding='utf-8')

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
            result = runner.invoke(
                rms,
                [
                    '--cwd',
                    str(project_dir),
                    'publish',
                    '--all',
                    '--docx',
                    '--docx-template',
                    str(custom_template),
                    '--output',
                    str(out_dir),
                ],
            )

        assert result.exit_code == 0, result.output
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args
        ref_doc = call_args.kwargs.get('reference_doc') or call_args[1].get('reference_doc')
        assert ref_doc == custom_template

    def test_docx_template_cli_none(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        runner = CliRunner()
        out_dir = project_dir / 'out'

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
            result = runner.invoke(
                rms,
                [
                    '--cwd',
                    str(project_dir),
                    'publish',
                    '--all',
                    '--docx',
                    '--docx-template',
                    'none',
                    '--output',
                    str(out_dir),
                ],
            )

        assert result.exit_code == 0, result.output
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args
        ref_doc = call_args.kwargs.get('reference_doc') or call_args[1].get('reference_doc')
        assert ref_doc is None

    def test_docx_template_config_default_template_none(self, project_dir):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        runner = CliRunner()
        out_dir = project_dir / 'out'

        # Create publish.yaml with docx-template.default-template = "none"
        dot_syntagmax = project_dir / '.syntagmax'
        publish_yaml = dot_syntagmax / 'publish.yaml'
        publish_yaml.write_text('docx-template:\n  default-template: "none"\n', encoding='utf-8')

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), patch('syntagmax.pandoc.convert', return_value=(True, 'ok')) as mock_convert:
            result = runner.invoke(rms, ['--cwd', str(project_dir), 'publish', '--all', '--docx', '--output', str(out_dir)])

        assert result.exit_code == 0, result.output
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args
        ref_doc = call_args.kwargs.get('reference_doc') or call_args[1].get('reference_doc')
        assert ref_doc is None

    def test_single_mode_conflicting_templates_warns(self, tmp_path):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        # Set up project with two records and conflicting templates
        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg = dot_syntagmax / 'config.toml'
        cfg.write_text(
            'base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n[[input]]\nname="rec2"\ndir="SRS"\ndriver="text"\natype="SRS"\n',
            encoding='utf-8',
        )

        # Create input dirs
        sys_dir = tmp_path / 'SYS'
        sys_dir.mkdir()
        (sys_dir / 'sys.md').write_text('[< ID=SYS-1 >>> X >]', encoding='utf-8')

        srs_dir = tmp_path / 'SRS'
        srs_dir.mkdir()
        (srs_dir / 'srs.md').write_text('[< ID=SRS-1 >>> Y >]', encoding='utf-8')

        # Create templates (relative to .syntagmax dir which is config root)
        tpl1 = dot_syntagmax / 'tpl1.dotm'
        tpl1.write_text('fake1', encoding='utf-8')
        tpl2 = dot_syntagmax / 'tpl2.dotm'
        tpl2.write_text('fake2', encoding='utf-8')

        # Publish config with conflicting overrides
        publish_yaml = dot_syntagmax / 'publish.yaml'
        publish_yaml.write_text(
            'docx-template:\n  overrides:\n    rec1: "tpl1.dotm"\n    rec2: "tpl2.dotm"\n',
            encoding='utf-8',
        )

        runner = CliRunner()
        out_file = tmp_path / 'out' / 'combined.md'

        with patch('syntagmax.pandoc.check_pandoc', return_value=True), patch('syntagmax.pandoc.convert', return_value=(True, 'ok')):
            result = runner.invoke(
                rms,
                [
                    '--cwd',
                    str(tmp_path),
                    'publish',
                    '--all',
                    '--single',
                    '--docx',
                    '--output',
                    str(out_file),
                ],
            )

        assert result.exit_code == 0, result.output
        assert 'conflicting' in result.output.lower() or 'Conflicting' in result.output
