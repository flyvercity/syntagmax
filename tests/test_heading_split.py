# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-07-16
# Description: Tests for ATX heading splitting in the Markdown extractor.

import pytest

from syntagmax.config import Config, InputRecord
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.blocks import TextBlock, ArtifactBlock
from syntagmax.params import Params


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
        'base = "."\n[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "SYS"\n',
        encoding='utf-8',
    )
    return Config(params=params, config_filename=cfg_path)


@pytest.fixture
def obsidian_config_with_markers(params, tmp_path):
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        'base = "."\n[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "SYS"\nmarkers = ["COM", "NOTE"]\n',
        encoding='utf-8',
    )
    return Config(params=params, config_filename=cfg_path)


@pytest.fixture
def input_record(tmp_path):
    return InputRecord(
        name='test',
        dir='.',
        record_base=tmp_path,
        filepaths=[],
        driver='obsidian',
        default_atype='SYS',
        marker='SYS',
    )


@pytest.fixture
def input_record_with_markers(tmp_path):
    return InputRecord(
        name='test',
        dir='.',
        record_base=tmp_path,
        filepaths=[],
        driver='obsidian',
        default_atype='SYS',
        marker='SYS',
        markers=['COM', 'NOTE'],
    )


class TestHeadingSplitBasic:
    """Basic heading splitting behaviour."""

    def test_single_heading_at_start(self, obsidian_config, input_record, tmp_path):
        """A heading at the start of a text block is split out."""
        content = "## Overview\n\nThis is body text.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        # Should be: HEADING block + body text block
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        assert len(text_blocks) == 2
        assert text_blocks[0].marker == 'HEADING'
        assert '## Overview' in text_blocks[0].content
        assert text_blocks[1].marker is None
        assert 'This is body text.' in text_blocks[1].content

    def test_multiple_headings(self, obsidian_config, input_record, tmp_path):
        """Multiple headings produce multiple heading blocks with body between them."""
        content = "## First\n\nBody one.\n\n## Second\n\nBody two.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        # Expect: H1, body1, H2, body2
        headings = [b for b in text_blocks if b.marker == 'HEADING']
        bodies = [b for b in text_blocks if b.marker is None]
        assert len(headings) == 2
        assert len(bodies) == 2
        assert '## First' in headings[0].content
        assert '## Second' in headings[1].content
        assert 'Body one.' in bodies[0].content
        assert 'Body two.' in bodies[1].content

    def test_consecutive_headings(self, obsidian_config, input_record, tmp_path):
        """Consecutive headings produce consecutive heading blocks."""
        content = "# Title\n## Section\n### Subsection\n\nBody text.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        headings = [b for b in text_blocks if b.marker == 'HEADING']
        assert len(headings) == 3
        assert '# Title' in headings[0].content
        assert '## Section' in headings[1].content
        assert '### Subsection' in headings[2].content

    def test_heading_levels(self, obsidian_config, input_record, tmp_path):
        """All heading levels (1-6) are recognised."""
        content = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        headings = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(headings) == 6


class TestHeadingSplitCodeBlockAwareness:
    """Headings inside fenced code blocks must NOT be split."""

    def test_heading_inside_code_block(self, obsidian_config, input_record, tmp_path):
        """A heading line inside a fenced code block stays in the text block."""
        content = "Some text.\n\n```\n## Not a heading\n```\n\nMore text.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        headings = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(headings) == 0

    def test_heading_after_code_block(self, obsidian_config, input_record, tmp_path):
        """A heading after a code block IS split."""
        content = "```\ncode\n```\n\n## Real Heading\n\nBody.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        headings = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(headings) == 1
        assert '## Real Heading' in headings[0].content


class TestHeadingSplitCommonMarkCompliance:
    """CommonMark compliance: at most 3 leading spaces."""

    def test_three_leading_spaces_is_heading(self, obsidian_config, input_record, tmp_path):
        """Up to 3 leading spaces is still a heading."""
        content = "   ## Indented Heading\n\nBody.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        headings = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(headings) == 1

    def test_four_leading_spaces_not_heading(self, obsidian_config, input_record, tmp_path):
        """4+ leading spaces is NOT a heading (indented code block)."""
        content = "    ## Not a heading\n\nBody.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        headings = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(headings) == 0


class TestHeadingSplitOffset:
    """Source offset correctness."""

    def test_offsets_are_correct(self, obsidian_config, input_record, tmp_path):
        """Source offsets match character positions in the file."""
        content = "## Heading\n\nBody text here.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        assert text_blocks[0].marker == 'HEADING'
        assert text_blocks[0].source_offset == 0
        assert text_blocks[1].marker is None
        assert text_blocks[1].source_offset == len('## Heading\n')

    def test_offsets_with_duplicate_lines(self, obsidian_config, input_record, tmp_path):
        """Offsets are correct even when the file has duplicate lines."""
        content = "## Same\n\ntext\n\n## Same\n\ntext\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        headings = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(headings) == 2
        assert headings[0].source_offset == 0
        # Second heading: after "## Same\n\ntext\n\n" = 8 + 1 + 4 + 1 + 1 = 15
        expected_offset = len("## Same\n\ntext\n\n")
        assert headings[1].source_offset == expected_offset


class TestHeadingSplitWhitespace:
    """Whitespace-only blocks are preserved."""

    def test_whitespace_between_headings_preserved(self, obsidian_config, input_record, tmp_path):
        """Blank lines between headings produce whitespace text blocks."""
        content = "## First\n\n\n## Second\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        headings = [b for b in text_blocks if b.marker == 'HEADING']
        whitespace_blocks = [b for b in text_blocks if b.marker is None]
        assert len(headings) == 2
        # The blank lines between headings form a whitespace block
        assert len(whitespace_blocks) == 1
        assert whitespace_blocks[0].content.strip() == ''


class TestHeadingSplitWithMarkers:
    """Heading splitting interacts correctly with fragment markers."""

    def test_heading_in_marked_block_not_split(self, obsidian_config_with_markers, input_record_with_markers, tmp_path):
        """Headings inside marked fragments (e.g. [COM]) are not split."""
        content = "[COM]\n## Heading inside comment\nSome comment text.\n[/COM]\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config_with_markers, input_record_with_markers)
        blocks = extractor.extract_blocks_from_file(filepath)

        # The [COM] block should contain the heading — not split
        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        heading_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(com_blocks) == 1
        assert '## Heading inside comment' in com_blocks[0].content
        assert len(heading_blocks) == 0

    def test_heading_outside_marked_block_is_split(self, obsidian_config_with_markers, input_record_with_markers, tmp_path):
        """Headings outside marked fragments ARE split."""
        content = "## Section Title\n\n[COM]\nA comment.\n[/COM]\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config_with_markers, input_record_with_markers)
        blocks = extractor.extract_blocks_from_file(filepath)

        heading_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(heading_blocks) == 1
        assert '## Section Title' in heading_blocks[0].content


class TestHeadingSplitWithArtifacts:
    """Heading splitting works correctly with artifact blocks."""

    def test_heading_between_artifacts(self, obsidian_config, input_record, tmp_path):
        """Headings between artifacts are correctly split."""
        content = (
            "[SYS]\nFirst requirement.\n[id] SYS-001\n```yaml\nattrs:\n  status: draft\n```\n\n"
            "## Next Section\n\nSome text.\n\n"
            "[SYS]\nSecond requirement.\n[id] SYS-002\n```yaml\nattrs:\n  status: draft\n```\n"
        )
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(obsidian_config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)

        artifacts = [b for b in blocks if isinstance(b, ArtifactBlock)]
        headings = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(artifacts) == 2
        assert len(headings) == 1
        assert '## Next Section' in headings[0].content


class TestHeadingSplitExcludeElements:
    """Integration with exclude_elements for headings."""

    def test_exclude_headings_string_drops_heading_block(self, params, tmp_path):
        """exclude_elements headings=string drops the entire HEADING block."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "SYS"\n'
            '[[input.exclude_elements]]\nname = "headings"\nmode = "string"\n',
            encoding='utf-8',
        )
        config = Config(params=params, config_filename=cfg_path)
        record = config.input_records()[0]

        content = "## Heading\n\nBody text.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(config, record)
        blocks = extractor.extract_blocks_from_file(filepath)

        headings = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(headings) == 0
        # Body text should still be present
        bodies = [b for b in blocks if isinstance(b, TextBlock) and b.marker is None]
        assert len(bodies) == 1
        assert 'Body text.' in bodies[0].content

    def test_exclude_headings_only_strips_prefix(self, params, tmp_path):
        """exclude_elements headings=only strips # prefix and converts to plain text."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = "."\n[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "SYS"\n'
            '[[input.exclude_elements]]\nname = "headings"\nmode = "only"\n',
            encoding='utf-8',
        )
        config = Config(params=params, config_filename=cfg_path)
        record = config.input_records()[0]

        content = "## My Heading\n\nBody text.\n"
        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(config, record)
        blocks = extractor.extract_blocks_from_file(filepath)

        # The heading should become a plain text block with marker=None
        headings = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'HEADING']
        assert len(headings) == 0
        # Should have body text and the converted heading as plain text
        plain_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker is None]
        # Check that one contains "My Heading" without "#"
        heading_text = [b for b in plain_blocks if 'My Heading' in b.content]
        assert len(heading_text) == 1
        assert not heading_text[0].content.startswith('#')
