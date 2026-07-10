# SPDX-License-Identifier: MIT
"""Tests for the simple block terminator feature: empty lines, headings, fragment markers, and EOF."""

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
        'base = "."\n[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\nmarkers = ["COM", "NOTE"]\n',
        encoding='utf-8',
    )
    return Config(params=params, config_filename=cfg_path)


@pytest.fixture
def input_record_with_markers(tmp_path):
    return InputRecord(
        name='test',
        dir='.',
        record_base=tmp_path,
        filepaths=[],
        driver='obsidian',
        default_atype='REQ',
        marker='REQ',
        markers=['COM', 'NOTE'],
    )


def _extract_blocks(config, record, tmp_path, content):
    f = tmp_path / 'test.md'
    f.write_text(content, encoding='utf-8')
    extractor = ObsidianExtractor(config, record)
    return extractor.extract_blocks_from_file(f)


class TestArtifactBlocks:
    """Test artifact block termination by various terminators."""

    def test_empty_line_terminates(self, obsidian_config, input_record_with_markers, tmp_path):
        """A single empty line terminates an artifact block when no [/TAG] or YAML is present."""
        content = '[REQ]\nThe system shall do X.\n[id] REQ-001\n\nMore text after.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]

        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'
        assert len(text_blocks) >= 1
        assert any('More text after' in b.content for b in text_blocks)

    def test_slash_tag_still_works(self, obsidian_config, input_record_with_markers, tmp_path):
        """Explicit [/REQ] still terminates correctly (backward compat)."""
        content = '[REQ]\nThe system shall do X.\n[id] REQ-001\n[/REQ]\nMore text.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_yaml_still_works(self, obsidian_config, input_record_with_markers, tmp_path):
        """YAML block still terminates correctly (backward compat)."""
        content = '[REQ]\nThe system shall do X.\n[id] REQ-001\n```yaml\nattrs:\n  status: active\n```'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_yaml_takes_priority_over_empty_line(self, obsidian_config, input_record_with_markers, tmp_path):
        """YAML block is found even if there's an empty line after it."""
        content = '[REQ]\nThe system shall do X.\n[id] REQ-001\n```yaml\nattrs:\n  status: active\n```\n\nMore text.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_multi_paragraph_with_slash_tag(self, obsidian_config, input_record_with_markers, tmp_path):
        """Multi-paragraph requirement with explicit [/REQ] works (empty lines inside don't terminate)."""
        content = '[REQ]\nParagraph one.\n\nParagraph two.\n[id] REQ-001\n[/REQ]\nAfter.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_multi_paragraph_with_yaml(self, obsidian_config, input_record_with_markers, tmp_path):
        """Multi-paragraph requirement with YAML block works (empty lines inside don't terminate)."""
        content = '[REQ]\nParagraph one.\n\nParagraph two.\n[id] REQ-001\n```yaml\nattrs:\n  status: active\n```\nAfter.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_heading_terminates(self, obsidian_config, input_record_with_markers, tmp_path):
        """A Markdown heading at BOL terminates the artifact block (context-aware)."""
        content = '[REQ]\nThe system shall do X.\n[id] REQ-001\n# Next Section\nMore text.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]

        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'
        # The heading should be in subsequent text (not consumed)
        assert any('# Next Section' in b.content for b in text_blocks)

    def test_obsidian_tag_does_not_terminate(self, obsidian_config, input_record_with_markers, tmp_path):
        """A line starting with # without a space (Obsidian tag) does NOT terminate."""
        content = '[REQ]\nThe system shall do X.\n#tag-name\n[id] REQ-001\n[/REQ]\nAfter.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_fragment_marker_terminates(self, obsidian_config, input_record_with_markers, tmp_path):
        """A fragment marker at BOL terminates the artifact block (context-aware)."""
        content = '[REQ]\nThe system shall do X.\n[id] REQ-001\n[COM]This is a comment[/COM]\nAfter.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_eof_terminates(self, obsidian_config, input_record_with_markers, tmp_path):
        """End of file terminates the artifact block when no other terminator is present."""
        content = '[REQ]\nThe system shall do X.\n[id] REQ-001'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_eof_without_trailing_newline(self, obsidian_config, input_record_with_markers, tmp_path):
        """End of file without trailing newline still extracts the artifact."""
        content = '[REQ]\nContent here\n[id] REQ-EOF'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-EOF'

    def test_multiple_consecutive_empty_lines(self, obsidian_config, input_record_with_markers, tmp_path):
        """Multiple consecutive empty lines are consumed as a single terminator."""
        content = '[REQ]\nContent.\n[id] REQ-001\n\n\n\nMore text.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]

        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'
        # All empty lines should be consumed; text after should not start with newlines
        after_blocks = [b for b in text_blocks if 'More text' in b.content]
        assert len(after_blocks) == 1
        assert after_blocks[0].content.startswith('More text')

    def test_crlf_empty_line_terminates(self, obsidian_config, input_record_with_markers, tmp_path):
        """Windows-style CRLF empty lines work as terminator."""
        content = '[REQ]\r\nContent.\r\n[id] REQ-001\r\n\r\nMore text.'
        f = tmp_path / 'test.md'
        f.write_text(content, encoding='utf-8', newline='')
        extractor = ObsidianExtractor(obsidian_config, input_record_with_markers)
        blocks = extractor.extract_blocks_from_file(f)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_consecutive_artifacts_with_empty_line(self, obsidian_config, input_record_with_markers, tmp_path):
        """Two artifacts separated by empty lines both parse correctly."""
        content = '[REQ]\nFirst.\n[id] REQ-001\n\n[REQ]\nSecond.\n[id] REQ-002\n\nAfter.'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 2
        assert artifact_blocks[0].artifact.aid == 'REQ-001'
        assert artifact_blocks[1].artifact.aid == 'REQ-002'

    def test_hash_inside_line_does_not_terminate(self, obsidian_config, input_record_with_markers, tmp_path):
        """A # inside a line (not at BOL) does not terminate."""
        content = '[REQ]\nValue is C# compatible.\n[id] REQ-001\n[/REQ]'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_fragment_marker_inside_content_does_not_terminate(self, obsidian_config, input_record_with_markers, tmp_path):
        """A fragment marker text inside content (not at BOL) does not terminate."""
        content = '[REQ]\nSee [COM] for details.\n[id] REQ-001\n[/REQ]'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'


class TestMarkedTextBlocks:
    """Test marked text block termination by empty lines."""

    def test_unclosed_marker_terminated_by_empty_line(self, obsidian_config, input_record_with_markers, tmp_path):
        """An unclosed [COM] is terminated by an empty line."""
        content = '[COM]comment text\n\nafter'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        assert len(com_blocks) == 1
        assert 'comment text' in com_blocks[0].content

    def test_closed_marker_still_works(self, obsidian_config, input_record_with_markers, tmp_path):
        """Closed [COM]...[/COM] still works (backward compat)."""
        content = '[COM]comment text[/COM] after'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        assert len(com_blocks) == 1
        assert com_blocks[0].content == 'comment text'

    def test_unclosed_multiline_terminated_by_empty_line(self, obsidian_config, input_record_with_markers, tmp_path):
        """Multiline unclosed marker terminated by empty line."""
        content = '[COM]line1\nline2\n\nafter'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        assert len(com_blocks) == 1
        assert 'line1' in com_blocks[0].content
        assert 'line2' in com_blocks[0].content

    def test_multi_paragraph_closed_marker(self, obsidian_config, input_record_with_markers, tmp_path):
        """Multi-paragraph comment with explicit [/COM] works correctly."""
        content = '[COM]para1\n\npara2[/COM] after'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        assert len(com_blocks) == 1
        assert 'para1' in com_blocks[0].content
        assert 'para2' in com_blocks[0].content

    def test_adjacent_unclosed_markers(self, obsidian_config, input_record_with_markers, tmp_path):
        """Adjacent unclosed markers on separate lines each get their own block."""
        content = '[COM]comment 1\n[NOTE]note 1\n\nafter'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        note_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'NOTE']

        assert len(com_blocks) == 1
        assert len(note_blocks) == 1

    def test_marked_text_block_followed_by_artifact(self, obsidian_config, input_record_with_markers, tmp_path):
        """Marked text block followed by artifact with empty line separation."""
        content = '[COM]comment\n\n[REQ]\nContent.\n[id] REQ-001\n\n'
        blocks = _extract_blocks(obsidian_config, input_record_with_markers, tmp_path, content)

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']

        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'
        assert len(com_blocks) == 1


class TestMarkerAttributeCollision:
    """Test that fragment markers colliding with metamodel attributes are rejected."""

    def test_marker_collides_with_attribute(self, params, tmp_path):
        """A fragment marker that matches a metamodel attribute name raises FatalError."""
        # Create metamodel file
        metamodel_path = tmp_path / 'project.syntagmax'
        metamodel_path.write_text(
            'artifact REQ:\n    id is string\n    attribute contents is mandatory string\n    attribute status is mandatory string\n',
            encoding='utf-8',
        )

        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n\n[metamodel]\nfilename = "project.syntagmax"\n\n'
            '[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\n'
            'markers = ["STATUS"]\n',
            encoding='utf-8',
        )

        with pytest.raises(FatalError) as exc_info:
            Config(params=params, config_filename=cfg_path)

        assert 'collides' in str(exc_info.value).lower() or 'status' in str(exc_info.value).lower()

    def test_marker_no_collision_succeeds(self, params, tmp_path):
        """A fragment marker that does not match any attribute loads successfully."""
        metamodel_path = tmp_path / 'project.syntagmax'
        metamodel_path.write_text(
            'artifact REQ:\n    id is string\n    attribute contents is mandatory string\n    attribute status is mandatory string\n',
            encoding='utf-8',
        )

        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n\n[metamodel]\nfilename = "project.syntagmax"\n\n'
            '[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\n'
            'markers = ["COM", "NOTE"]\n',
            encoding='utf-8',
        )

        config = Config(params=params, config_filename=cfg_path)
        assert config.input_records()[0].markers == ['COM', 'NOTE']

    def test_collision_case_insensitive(self, params, tmp_path):
        """Collision check is case-insensitive."""
        metamodel_path = tmp_path / 'project.syntagmax'
        metamodel_path.write_text(
            'artifact REQ:\n    id is string\n    attribute contents is mandatory string\n    attribute status is mandatory string\n',
            encoding='utf-8',
        )

        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n\n[metamodel]\nfilename = "project.syntagmax"\n\n'
            '[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\n'
            'markers = ["status"]\n',
            encoding='utf-8',
        )

        with pytest.raises(FatalError):
            Config(params=params, config_filename=cfg_path)
