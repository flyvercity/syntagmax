# SPDX-License-Identifier: MIT
# Tests for strict_line_breaks setting in Obsidian driver

import json
import pytest
from pydantic import ValidationError

from syntagmax.config import Config, ObsidianDriverConfig
from syntagmax.extractors.markdown import apply_soft_line_breaks
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.obsidian_settings import read_obsidian_strict_line_breaks
from syntagmax.params import Params
from syntagmax.errors import FatalError
from syntagmax.blocks import TextBlock, ArtifactBlock


@pytest.fixture
def params():
    return Params(verbose=False, render_tree=False, ai=False, output='console')


# ============================================================
# Task 1: ObsidianDriverConfig field validation
# ============================================================


class TestStrictLineBreaksFieldValidation:
    """Test that strict_line_breaks field accepts valid values and rejects invalid ones."""

    def test_default_is_on(self):
        cfg = ObsidianDriverConfig()
        assert cfg.strict_line_breaks == 'on'

    @pytest.mark.parametrize(
        'value,expected',
        [
            ('on', 'on'),
            ('ON', 'on'),
            ('On', 'on'),
            ('off', 'off'),
            ('OFF', 'off'),
            ('true', 'true'),
            ('TRUE', 'true'),
            ('false', 'false'),
            ('FALSE', 'false'),
            ('auto', 'auto'),
            ('AUTO', 'auto'),
        ],
    )
    def test_valid_string_values(self, value, expected):
        cfg = ObsidianDriverConfig(strict_line_breaks=value)
        assert cfg.strict_line_breaks == expected

    def test_native_bool_true(self):
        cfg = ObsidianDriverConfig(strict_line_breaks=True)
        assert cfg.strict_line_breaks == 'true'

    def test_native_bool_false(self):
        cfg = ObsidianDriverConfig(strict_line_breaks=False)
        assert cfg.strict_line_breaks == 'false'

    def test_invalid_value_raises(self):
        with pytest.raises(ValidationError):
            ObsidianDriverConfig(strict_line_breaks='maybe')

    def test_invalid_value_garbage(self):
        with pytest.raises(ValidationError):
            ObsidianDriverConfig(strict_line_breaks='yes')

    def test_parsed_from_toml_string(self, params, tmp_path):
        """Verify that TOML config with string value parses correctly."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nstrict_line_breaks = "off"\n',
            encoding='utf-8',
        )
        req_dir = tmp_path / '..' / 'REQ'
        req_dir.mkdir(parents=True, exist_ok=True)

        config = Config(params=params, config_filename=cfg_path)
        assert config.obsidian_driver_config.strict_line_breaks == 'off'

    def test_parsed_from_toml_native_bool(self, params, tmp_path):
        """Verify that TOML config with native boolean parses correctly."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nstrict_line_breaks = false\n',
            encoding='utf-8',
        )
        req_dir = tmp_path / '..' / 'REQ'
        req_dir.mkdir(parents=True, exist_ok=True)

        config = Config(params=params, config_filename=cfg_path)
        assert config.obsidian_driver_config.strict_line_breaks == 'false'


# ============================================================
# Task 2: Cross-field validation (auto + integration)
# ============================================================


class TestAutoRequiresIntegration:
    """Test that strict_line_breaks = 'auto' without integration raises FatalError."""

    def test_auto_without_integration_raises(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nstrict_line_breaks = "auto"\n',
            encoding='utf-8',
        )
        req_dir = tmp_path / '..' / 'REQ'
        req_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(FatalError) as exc_info:
            Config(params=params, config_filename=cfg_path)
        assert 'strict_line_breaks = "auto" requires integration = true' in str(exc_info.value)

    def test_auto_with_integration_passes(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n'
            '[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n'
            '[drivers.obsidian]\nstrict_line_breaks = "auto"\nintegration = true\n',
            encoding='utf-8',
        )
        req_dir = tmp_path / '..' / 'REQ'
        req_dir.mkdir(parents=True, exist_ok=True)

        # Should not raise — even without app.json (auto resolves lazily)
        config = Config(params=params, config_filename=cfg_path)
        assert config.obsidian_driver_config.strict_line_breaks == 'auto'


# ============================================================
# Task 3: read_obsidian_strict_line_breaks()
# ============================================================


class TestReadObsidianStrictLineBreaks:
    """Test the obsidian_settings reader for strictLineBreaks."""

    def test_reads_true(self, tmp_path):
        obsidian_dir = tmp_path / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'strictLineBreaks': True}), encoding='utf-8')
        assert read_obsidian_strict_line_breaks(tmp_path) is True

    def test_reads_false(self, tmp_path):
        obsidian_dir = tmp_path / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'strictLineBreaks': False}), encoding='utf-8')
        assert read_obsidian_strict_line_breaks(tmp_path) is False

    def test_key_absent_returns_none(self, tmp_path, caplog):
        obsidian_dir = tmp_path / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'attachmentFolderPath': 'attachments'}), encoding='utf-8')
        result = read_obsidian_strict_line_breaks(tmp_path)
        assert result is None
        assert 'strictLineBreaks not set' in caplog.text

    def test_missing_app_json_returns_none(self, tmp_path, caplog):
        result = read_obsidian_strict_line_breaks(tmp_path)
        assert result is None
        assert 'not found' in caplog.text

    def test_malformed_json_returns_none(self, tmp_path, caplog):
        obsidian_dir = tmp_path / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text('{ broken', encoding='utf-8')
        result = read_obsidian_strict_line_breaks(tmp_path)
        assert result is None
        assert 'malformed JSON' in caplog.text

    def test_root_override(self, tmp_path):
        custom_dir = tmp_path / 'custom-obsidian'
        custom_dir.mkdir()
        (custom_dir / 'app.json').write_text(json.dumps({'strictLineBreaks': False}), encoding='utf-8')
        result = read_obsidian_strict_line_breaks(tmp_path, root_override='custom-obsidian')
        assert result is False


# ============================================================
# Task 4: resolve_strict_line_breaks()
# ============================================================


class TestResolveStrictLineBreaks:
    """Test the Config.resolve_strict_line_breaks() method."""

    def test_on_returns_true(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nstrict_line_breaks = "on"\n',
            encoding='utf-8',
        )
        (tmp_path / '..' / 'REQ').mkdir(parents=True, exist_ok=True)
        config = Config(params=params, config_filename=cfg_path)
        assert config.resolve_strict_line_breaks() is True

    def test_off_returns_false(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nstrict_line_breaks = "off"\n',
            encoding='utf-8',
        )
        (tmp_path / '..' / 'REQ').mkdir(parents=True, exist_ok=True)
        config = Config(params=params, config_filename=cfg_path)
        assert config.resolve_strict_line_breaks() is False

    def test_true_returns_true(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nstrict_line_breaks = true\n',
            encoding='utf-8',
        )
        (tmp_path / '..' / 'REQ').mkdir(parents=True, exist_ok=True)
        config = Config(params=params, config_filename=cfg_path)
        assert config.resolve_strict_line_breaks() is True

    def test_false_returns_false(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nstrict_line_breaks = false\n',
            encoding='utf-8',
        )
        (tmp_path / '..' / 'REQ').mkdir(parents=True, exist_ok=True)
        config = Config(params=params, config_filename=cfg_path)
        assert config.resolve_strict_line_breaks() is False

    def test_auto_reads_from_app_json_true(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n'
            '[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n'
            '[drivers.obsidian]\nstrict_line_breaks = "auto"\nintegration = true\n',
            encoding='utf-8',
        )
        base_dir = (tmp_path / '..').resolve()
        (base_dir / 'REQ').mkdir(parents=True, exist_ok=True)
        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir(exist_ok=True)
        (obsidian_dir / 'app.json').write_text(json.dumps({'strictLineBreaks': True}), encoding='utf-8')
        config = Config(params=params, config_filename=cfg_path)
        assert config.resolve_strict_line_breaks() is True

    def test_auto_reads_from_app_json_false(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n'
            '[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n'
            '[drivers.obsidian]\nstrict_line_breaks = "auto"\nintegration = true\n',
            encoding='utf-8',
        )
        base_dir = (tmp_path / '..').resolve()
        (base_dir / 'REQ').mkdir(parents=True, exist_ok=True)
        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir(exist_ok=True)
        (obsidian_dir / 'app.json').write_text(json.dumps({'strictLineBreaks': False}), encoding='utf-8')
        config = Config(params=params, config_filename=cfg_path)
        assert config.resolve_strict_line_breaks() is False

    def test_auto_defaults_to_true_when_key_missing(self, params, tmp_path, caplog):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n'
            '[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n'
            '[drivers.obsidian]\nstrict_line_breaks = "auto"\nintegration = true\n',
            encoding='utf-8',
        )
        base_dir = (tmp_path / '..').resolve()
        (base_dir / 'REQ').mkdir(parents=True, exist_ok=True)
        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir(exist_ok=True)
        (obsidian_dir / 'app.json').write_text(json.dumps({'attachmentFolderPath': 'imgs'}), encoding='utf-8')
        config = Config(params=params, config_filename=cfg_path)
        assert config.resolve_strict_line_breaks() is True
        assert 'defaulting to strict mode ON' in caplog.text

    def test_result_is_cached(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nstrict_line_breaks = "off"\n',
            encoding='utf-8',
        )
        (tmp_path / '..' / 'REQ').mkdir(parents=True, exist_ok=True)
        config = Config(params=params, config_filename=cfg_path)
        result1 = config.resolve_strict_line_breaks()
        result2 = config.resolve_strict_line_breaks()
        assert result1 is result2 is False


# ============================================================
# Task 5: apply_soft_line_breaks() transformation
# ============================================================


class TestApplySoftLineBreaks:
    """Test the line-break transformation function."""

    def test_empty_string(self):
        assert apply_soft_line_breaks('') == ''

    def test_no_newlines(self):
        assert apply_soft_line_breaks('hello world') == 'hello world'

    def test_single_newline_between_text(self):
        assert apply_soft_line_breaks('line1\nline2\n') == 'line1  \nline2  \n'

    def test_paragraph_break_preserved(self):
        result = apply_soft_line_breaks('line1\n\nparagraph2\n')
        assert result == 'line1\n\nparagraph2  \n'

    def test_line_before_empty_line_not_modified(self):
        result = apply_soft_line_breaks('line1\n\nline2\n')
        # line1 is followed by empty line → not modified
        assert result == 'line1\n\nline2  \n'

    def test_whitespace_only_line_preserved(self):
        result = apply_soft_line_breaks('line1\n   \nline2\n')
        # line1 is followed by whitespace-only → not modified
        # whitespace-only line itself not modified
        assert result == 'line1\n   \nline2  \n'

    def test_already_has_trailing_spaces(self):
        result = apply_soft_line_breaks('already  \nnext\n')
        assert result == 'already  \nnext  \n'

    def test_already_has_backslash(self):
        result = apply_soft_line_breaks('line\\\nnext\n')
        assert result == 'line\\\nnext  \n'

    def test_code_block_untouched(self):
        text = 'before\n```\ncode line1\ncode line2\n```\nafter\n'
        result = apply_soft_line_breaks(text)
        assert '```\ncode line1\ncode line2\n```' in result
        assert result.startswith('before  \n```\n')
        assert result.endswith('```\nafter  \n')

    def test_heading_not_modified(self):
        result = apply_soft_line_breaks('# Title\ntext\n')
        assert result == '# Title\ntext  \n'

    def test_table_row_not_modified(self):
        result = apply_soft_line_breaks('| col1 | col2 |\ntext\n')
        assert result == '| col1 | col2 |\ntext  \n'

    def test_unordered_list_not_modified(self):
        result = apply_soft_line_breaks('- item1\n- item2\ntext\n')
        assert result == '- item1\n- item2\ntext  \n'

    def test_ordered_list_not_modified(self):
        result = apply_soft_line_breaks('1. item\n2. item\ntext\n')
        assert result == '1. item\n2. item\ntext  \n'

    def test_thematic_break_not_modified(self):
        result = apply_soft_line_breaks('text\n---\nmore\n')
        assert result == 'text  \n---\nmore  \n'

    def test_html_block_not_modified(self):
        result = apply_soft_line_breaks('<div>\ntext\n')
        assert result == '<div>\ntext  \n'

    def test_crlf_preserved(self):
        result = apply_soft_line_breaks('line1\r\nline2\r\n')
        assert result == 'line1  \r\nline2  \r\n'

    def test_crlf_paragraph_break(self):
        result = apply_soft_line_breaks('line1\r\n\r\nline2\r\n')
        assert result == 'line1\r\n\r\nline2  \r\n'

    def test_last_line_without_newline(self):
        result = apply_soft_line_breaks('line1\nline2')
        # line2 has no trailing newline, so no transformation for it
        assert result == 'line1  \nline2'

    def test_multiple_paragraphs(self):
        text = 'p1 line1\np1 line2\n\np2 line1\np2 line2\n'
        result = apply_soft_line_breaks(text)
        assert result == 'p1 line1  \np1 line2\n\np2 line1  \np2 line2  \n'

    def test_mixed_block_and_text(self):
        text = '# Heading\nsome text\nmore text\n\n- list\n'
        result = apply_soft_line_breaks(text)
        assert result == '# Heading\nsome text  \nmore text\n\n- list\n'


# ============================================================
# Task 6: ObsidianExtractor integration
# ============================================================


class TestObsidianExtractorLineBreaks:
    """Test that ObsidianExtractor applies line break transformation correctly."""

    def _make_config(self, params, tmp_path, strict_line_breaks='off'):
        # Config file sits in tmp_path, with base="." so base_dir = tmp_path
        # REQ directory lives inside tmp_path
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            f'base = "."\n'
            f'[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n'
            f'[drivers.obsidian]\nstrict_line_breaks = "{strict_line_breaks}"\n',
            encoding='utf-8',
        )
        req_dir = tmp_path / 'REQ'
        req_dir.mkdir(parents=True, exist_ok=True)
        return Config(params=params, config_filename=cfg_path), req_dir

    def test_off_transforms_text_blocks(self, params, tmp_path):
        config, req_dir = self._make_config(params, tmp_path, 'off')
        record = config.input_records()[0]
        extractor = ObsidianExtractor(config, record, config.metamodel)

        md_file = req_dir / 'test.md'
        md_file.write_text(
            'First line\nSecond line\n\n[REQ]\nContent line1\nContent line2\n[id] REQ-1\n[/REQ]\n',
            encoding='utf-8',
        )

        blocks = extractor.extract_blocks_from_file(md_file)

        # Find text block
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        assert len(text_blocks) >= 1
        # First text block should have transformed newlines
        assert 'First line  \n' in text_blocks[0].content

        # Note: Artifact contents field is collapsed by the Lark parser
        # (newlines become spaces during parsing), so the transformation
        # cannot affect it. The transformation works on TextBlock content
        # which retains original newlines.

    def test_on_does_not_transform(self, params, tmp_path):
        config, req_dir = self._make_config(params, tmp_path, 'on')
        record = config.input_records()[0]
        extractor = ObsidianExtractor(config, record, config.metamodel)

        md_file = req_dir / 'test.md'
        md_file.write_text(
            'First line\nSecond line\n\n[REQ]\nContent line1\nContent line2\n[id] REQ-1\n[/REQ]\n',
            encoding='utf-8',
        )

        blocks = extractor.extract_blocks_from_file(md_file)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        assert len(text_blocks) >= 1
        # No transformation applied
        assert '  \n' not in text_blocks[0].content

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        contents = artifact_blocks[0].artifact.fields['contents']
        assert '  \n' not in contents

    def test_code_blocks_in_requirements_untouched(self, params, tmp_path):
        config, req_dir = self._make_config(params, tmp_path, 'off')
        record = config.input_records()[0]
        extractor = ObsidianExtractor(config, record, config.metamodel)

        md_file = req_dir / 'test.md'
        md_file.write_text(
            'Text with\ncode block:\n```\ncode line1\ncode line2\n```\nafter code\n',
            encoding='utf-8',
        )

        blocks = extractor.extract_blocks_from_file(md_file)
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        assert len(text_blocks) >= 1
        content = text_blocks[0].content
        # Code block lines should NOT have trailing spaces
        assert 'code line1\ncode line2\n' in content
        # But non-code lines should
        assert 'Text with  \n' in content
