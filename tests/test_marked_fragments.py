# SPDX-License-Identifier: MIT
import pytest

from syntagmax.config import Config, InputRecord
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.blocks import TextBlock, ArtifactBlock
from syntagmax.params import Params
from syntagmax.errors import FatalError


@pytest.fixture
def params():
    return Params(
        verbose=False,
        render_tree=False,
        ai=False,
        output='console',
        cwd='.',
        no_git=True,
        allow_dirty_worktree=True,
        suppress_tracing=True,
    )


@pytest.fixture
def obsidian_config(params, tmp_path):
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        'base = "."\n[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "SYS"\nmarkers = ["COM", "NOTE"]\n',
        encoding='utf-8',
    )
    return Config(params=params, config_filename=cfg_path)


@pytest.fixture
def input_record_with_markers(tmp_path):
    return InputRecord(
        name='test',
        record_base=tmp_path,
        filepaths=[],
        driver='obsidian',
        default_atype='SYS',
        marker='SYS',
        markers=['COM', 'NOTE'],
    )


class TestTextBlockMarkerField:
    def test_default_marker_is_none(self):
        block = TextBlock(content='hello')
        assert block.marker is None

    def test_marker_field_set(self):
        block = TextBlock(content='comment text', marker='COM')
        assert block.marker == 'COM'
        assert block.content == 'comment text'


class TestConfigMarkerValidation:
    def test_valid_markers_load(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "t"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\nmarkers = ["COM", "NOTE"]\n',
            encoding='utf-8',
        )
        config = Config(params=params, config_filename=cfg_path)
        assert config.input_records()[0].markers == ['COM', 'NOTE']

    def test_collision_with_artifact_marker_raises(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "t"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\nmarkers = ["REQ"]\n',
            encoding='utf-8',
        )
        with pytest.raises(FatalError):
            Config(params=params, config_filename=cfg_path)

    def test_collision_case_insensitive(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "t"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\nmarkers = ["req"]\n',
            encoding='utf-8',
        )
        with pytest.raises(FatalError):
            Config(params=params, config_filename=cfg_path)

    def test_non_obsidian_driver_raises(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "t"\ndir = "."\ndriver = "text"\natype = "SRC"\nmarkers = ["COM"]\n',
            encoding='utf-8',
        )
        with pytest.raises(FatalError):
            Config(params=params, config_filename=cfg_path)

    def test_invalid_marker_name_raises(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "t"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\nmarkers = ["COM!", "NOTE"]\n',
            encoding='utf-8',
        )
        with pytest.raises(FatalError):
            Config(params=params, config_filename=cfg_path)

    def test_duplicate_markers_raises(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "t"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\nmarkers = ["COM", "com"]\n',
            encoding='utf-8',
        )
        with pytest.raises(FatalError):
            Config(params=params, config_filename=cfg_path)

    def test_markers_stored_uppercase(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "t"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\nmarkers = ["com", "Note"]\n',
            encoding='utf-8',
        )
        config = Config(params=params, config_filename=cfg_path)
        assert config.input_records()[0].markers == ['COM', 'NOTE']


class TestFragmentSplitting:
    def _extract_blocks(self, config, record, tmp_path, content):
        f = tmp_path / 'test.md'
        f.write_text(content, encoding='utf-8')
        extractor = ObsidianExtractor(config, record)
        return extractor.extract_blocks_from_file(f)

    def test_single_marker(self, obsidian_config, input_record_with_markers, tmp_path):
        content = 'Before [COM]comment text[/COM] after'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        assert len(blocks) == 3
        assert isinstance(blocks[0], TextBlock) and blocks[0].marker is None
        assert blocks[0].content == 'Before '
        assert isinstance(blocks[1], TextBlock) and blocks[1].marker == 'COM'
        assert blocks[1].content == 'comment text'
        assert isinstance(blocks[2], TextBlock) and blocks[2].marker is None
        assert blocks[2].content == ' after'

    def test_multiple_different_markers(self, obsidian_config, input_record_with_markers, tmp_path):
        content = '[COM]a comment[/COM] gap [NOTE]a note[/NOTE]'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        assert len(blocks) == 3
        assert blocks[0].marker == 'COM' and blocks[0].content == 'a comment'
        assert blocks[1].marker is None and blocks[1].content == ' gap '
        assert blocks[2].marker == 'NOTE' and blocks[2].content == 'a note'

    def test_marker_at_start_of_file(self, obsidian_config, input_record_with_markers, tmp_path):
        content = '[COM]starts here[/COM] rest'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        assert len(blocks) == 2
        assert blocks[0].marker == 'COM' and blocks[0].content == 'starts here'
        assert blocks[1].marker is None and blocks[1].content == ' rest'

    def test_marker_at_end_of_file(self, obsidian_config, input_record_with_markers, tmp_path):
        content = 'start [NOTE]ends here[/NOTE]'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        assert len(blocks) == 2
        assert blocks[0].marker is None and blocks[0].content == 'start '
        assert blocks[1].marker == 'NOTE' and blocks[1].content == 'ends here'

    def test_adjacent_markers_no_gap(self, obsidian_config, input_record_with_markers, tmp_path):
        content = '[COM]first[/COM][NOTE]second[/NOTE]'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        assert len(blocks) == 2
        assert blocks[0].marker == 'COM' and blocks[0].content == 'first'
        assert blocks[1].marker == 'NOTE' and blocks[1].content == 'second'

    def test_case_insensitivity(self, obsidian_config, input_record_with_markers, tmp_path):
        content = '[com]lower[/COM] [Com]mixed[/com] [NOTE]upper[/note]'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        assert len(blocks) == 5
        assert blocks[0].marker == 'COM' and blocks[0].content == 'lower'
        assert blocks[1].marker is None and blocks[1].content == ' '
        assert blocks[2].marker == 'COM' and blocks[2].content == 'mixed'
        assert blocks[3].marker is None and blocks[3].content == ' '
        assert blocks[4].marker == 'NOTE' and blocks[4].content == 'upper'

    def test_empty_marker_content(self, obsidian_config, input_record_with_markers, tmp_path):
        content = 'before[COM][/COM]after'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        # Empty content marker still produces a TextBlock with empty content
        assert len(blocks) == 3
        assert blocks[0].marker is None and blocks[0].content == 'before'
        assert blocks[1].marker == 'COM' and blocks[1].content == ''
        assert blocks[2].marker is None and blocks[2].content == 'after'

    def test_unmarked_text_has_none_marker(self, obsidian_config, input_record_with_markers, tmp_path):
        content = 'plain text without any markers'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        assert len(blocks) == 1
        assert isinstance(blocks[0], TextBlock)
        assert blocks[0].marker is None
        assert blocks[0].content == 'plain text without any markers'

    def test_markers_dont_interfere_with_artifacts(self, obsidian_config, input_record_with_markers, tmp_path):
        content = '[COM]comment[/COM]\n[SYS]\nrequirement body\n[id] SYS-001\n[/SYS]\n[NOTE]a note[/NOTE]'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        # Should have: COM text, newline text (unmarked), artifact, NOTE text
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]

        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'SYS-001'

        com_blocks = [b for b in text_blocks if b.marker == 'COM']
        note_blocks = [b for b in text_blocks if b.marker == 'NOTE']
        assert len(com_blocks) == 1 and com_blocks[0].content == 'comment'
        assert len(note_blocks) == 1 and note_blocks[0].content == 'a note'

    def test_multiline_marker_content(self, obsidian_config, input_record_with_markers, tmp_path):
        content = '[COM]line one\nline two\nline three[/COM]'
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        assert len(blocks) == 1
        assert blocks[0].marker == 'COM'
        assert blocks[0].content == 'line one\nline two\nline three'

    def test_no_markers_configured_no_splitting(self, params, tmp_path):
        """When no markers configured, TextBlocks are not split."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "t"\ndir = "."\ndriver = "obsidian"\natype = "SYS"\n',
            encoding='utf-8',
        )
        config = Config(params=params, config_filename=cfg_path)
        record = config.input_records()[0]

        f = tmp_path / 'test.md'
        f.write_text('[COM]this stays as plain text[/COM]', encoding='utf-8')
        extractor = ObsidianExtractor(config, record)
        blocks = extractor.extract_blocks_from_file(f)

        assert len(blocks) == 1
        assert isinstance(blocks[0], TextBlock)
        assert blocks[0].marker is None
        assert '[COM]' in blocks[0].content

    def test_spec_example(self, obsidian_config, input_record_with_markers, tmp_path):
        """Test the example from the spec document."""
        content = 'This is a sample preamble text. [COM]This is a special comment text [/COM].\n[note]This a a special note text[/note]\nSome more text\n[SYS]\nThis is a text for the requirement\n[ID] SYS-000\n[/SYS]\n'  # noqa: E501
        blocks = self._extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        # Find all block types
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]

        # Should have one artifact
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'SYS-000'

        # Should have COM and NOTE markers
        com_blocks = [b for b in text_blocks if b.marker == 'COM']
        note_blocks = [b for b in text_blocks if b.marker == 'NOTE']
        regular_blocks = [b for b in text_blocks if b.marker is None]

        assert len(com_blocks) == 1
        assert 'special comment text' in com_blocks[0].content
        assert len(note_blocks) == 1
        assert 'special note text' in note_blocks[0].content
        assert len(regular_blocks) >= 1
