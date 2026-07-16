# SPDX-License-Identifier: MIT
"""Tests for the edit markers renumber command."""

import textwrap

import pytest

from syntagmax.blocks import TextBlock
from syntagmax.config import Config
from syntagmax.edit_markers import renumber_markers, _parse_numeric_id
from syntagmax.extract import EXTRACTORS
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


def _make_project(tmp_path, config_text, files):
    """Helper to set up a project with config and markdown files."""
    project_dir = tmp_path / 'project'
    project_dir.mkdir()
    docs_dir = project_dir / 'docs'
    docs_dir.mkdir()

    config_file = project_dir / 'config.toml'
    config_file.write_text(textwrap.dedent(config_text).strip(), encoding='utf-8')

    for filename, content in files.items():
        filepath = docs_dir / filename
        filepath.write_text(content, encoding='utf-8')

    return project_dir, config_file


# --- Unit tests for _parse_numeric_id ---


class TestParseNumericId:
    def test_valid_integer(self):
        assert _parse_numeric_id('5') == 5

    def test_zero(self):
        assert _parse_numeric_id('0') == 0

    def test_leading_zeros(self):
        assert _parse_numeric_id('005') == 5

    def test_negative(self):
        assert _parse_numeric_id('-1') is None

    def test_non_numeric(self):
        assert _parse_numeric_id('intro') is None

    def test_mixed(self):
        assert _parse_numeric_id('3a') is None

    def test_empty(self):
        assert _parse_numeric_id('') is None

    def test_none(self):
        assert _parse_numeric_id(None) is None


# --- Offset tracking tests ---


class TestOffsetTracking:
    """Verify that source_offset is correctly propagated to TextBlocks."""

    def test_closed_marker_offset(self, params, tmp_path):
        """Closed marker [COM]...[/COM] gets correct source_offset."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': 'Hello [COM]comment[/COM] world',
            },
        )

        config = Config(params=params, config_filename=config_file)
        record = config.input_records()[0]
        extractor = EXTRACTORS[record.driver](config, record, config.metamodel)
        blocks = extractor.extract_blocks_from_file(project_dir / 'docs' / 'test.md')

        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        assert len(com_blocks) == 1
        assert com_blocks[0].source_offset == 6  # 'Hello ' is 6 chars, then [COM] starts

    def test_unclosed_marker_offset(self, params, tmp_path):
        """Unclosed marker gets correct source_offset."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': 'Preamble\n[COM]unclosed content\n\nAfter',
            },
        )

        config = Config(params=params, config_filename=config_file)
        record = config.input_records()[0]
        extractor = EXTRACTORS[record.driver](config, record, config.metamodel)
        blocks = extractor.extract_blocks_from_file(project_dir / 'docs' / 'test.md')

        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        assert len(com_blocks) == 1
        # 'Preamble\n' is 9 chars, then [COM] starts at offset 9
        assert com_blocks[0].source_offset == 9

    def test_line_prefix_marker_offset(self, params, tmp_path):
        """Line-prefix marker gets correct source_offset."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM] line prefix content',
            },
        )

        config = Config(params=params, config_filename=config_file)
        record = config.input_records()[0]
        extractor = EXTRACTORS[record.driver](config, record, config.metamodel)
        blocks = extractor.extract_blocks_from_file(project_dir / 'docs' / 'test.md')

        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        assert len(com_blocks) == 1
        assert com_blocks[0].source_offset == 0

    def test_explicit_id_has_offset(self, params, tmp_path):
        """Marker with explicit ID still gets source_offset."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM 5]existing id[/COM]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        record = config.input_records()[0]
        extractor = EXTRACTORS[record.driver](config, record, config.metamodel)
        blocks = extractor.extract_blocks_from_file(project_dir / 'docs' / 'test.md')

        com_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker == 'COM']
        assert len(com_blocks) == 1
        assert com_blocks[0].explicit_id is True
        assert com_blocks[0].id == '5'
        assert com_blocks[0].source_offset == 0


# --- Core renumber logic tests ---


class TestRenumberBasic:
    """Basic renumbering behavior."""

    def test_single_unmarked_block_gets_id_1(self, params, tmp_path):
        """A single unmarked COM block gets ID 1 when no existing IDs."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM]some comment[/COM]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM 1]some comment[/COM]' in content

    def test_starts_after_max_existing(self, params, tmp_path):
        """New IDs start from max existing + 1."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM 5]existing[/COM]\n[COM]new one[/COM]\n[COM]new two[/COM]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM 5]existing[/COM]' in content
        assert '[COM 6]new one[/COM]' in content
        assert '[COM 7]new two[/COM]' in content

    def test_independent_numbering_per_marker_type(self, params, tmp_path):
        """Each marker type has independent numbering."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM", "NOTE"]
        """,
            {
                'test.md': '[COM 3]existing com[/COM]\n[COM]new com[/COM]\n[NOTE]new note[/NOTE]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM 3]existing com[/COM]' in content
        assert '[COM 4]new com[/COM]' in content
        assert '[NOTE 1]new note[/NOTE]' in content  # NOTE starts from 1

    def test_existing_ids_preserved(self, params, tmp_path):
        """Blocks with explicit IDs are never modified."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM 2]keep this[/COM]\n[COM intro]also keep[/COM]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM 2]keep this[/COM]' in content
        assert '[COM intro]also keep[/COM]' in content

    def test_non_numeric_id_does_not_affect_max(self, params, tmp_path):
        """Non-numeric IDs don't contribute to max computation."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM intro]text[/COM]\n[COM]new[/COM]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM intro]text[/COM]' in content
        assert '[COM 1]new[/COM]' in content  # starts from 1, not affected by 'intro'


class TestCasePreservation:
    """Test that original marker casing is preserved."""

    def test_lowercase_preserved(self, params, tmp_path):
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[com]lowercase[/com]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[com 1]lowercase[/com]' in content

    def test_mixed_case_preserved(self, params, tmp_path):
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[Com]mixed case[/Com]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[Com 1]mixed case[/Com]' in content


class TestMarkerFormats:
    """Test all three marker formats are handled correctly."""

    def test_closed_format(self, params, tmp_path):
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': 'Before [COM]closed content[/COM] after',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM 1]closed content[/COM]' in content

    def test_unclosed_format(self, params, tmp_path):
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': 'Preamble\n[COM]unclosed content\n\nAfter paragraph',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM 1]unclosed content' in content

    def test_line_prefix_format(self, params, tmp_path):
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM] line prefix content',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        # [COM] becomes [COM 1] — the space before content is part of the original format
        assert '[COM 1]' in content

    def test_all_formats_in_one_file(self, params, tmp_path):
        """Mix of all three formats in a single file."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM", "NOTE"]
        """,
            {
                'test.md': 'Intro [COM]closed com[/COM] text\n[NOTE]unclosed note\n\n[COM] prefix com',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM 1]closed com[/COM]' in content
        assert '[NOTE 1]unclosed note' in content
        assert '[COM 2]' in content


class TestCodeBlockSafety:
    """Verify behavior with markers inside code blocks.

    NOTE: The fragment marker splitter (_split_text_block_by_markers) does NOT
    currently skip code blocks. This is a pre-existing limitation. Markers inside
    fenced code blocks ARE extracted and thus WILL be renumbered. This test
    documents the current behavior. A future improvement to the splitter could
    add code-block awareness, which would automatically fix renumber behavior.
    """

    def test_marker_in_code_block_is_renumbered(self, params, tmp_path):
        """Literal [COM] inside a fenced code block is currently renumbered
        (known limitation of fragment marker splitting)."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM]real comment[/COM]\n\n```\n[COM]code example[/COM]\n```\n',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        # Both get renumbered (known limitation)
        assert '[COM 1]real comment[/COM]' in content
        assert '[COM 2]code example[/COM]' in content


class TestDryRun:
    """Dry-run mode does not modify files."""

    def test_dry_run_no_file_changes(self, params, tmp_path):
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM]some content[/COM]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config, dry_run=True)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert content == '[COM]some content[/COM]'  # unchanged


class TestSectionFilter:
    """Test --section filtering."""

    def test_section_filter(self, params, tmp_path):
        """Only the targeted section is renumbered."""
        project_dir = tmp_path / 'project'
        project_dir.mkdir()
        docs_dir = project_dir / 'docs'
        docs_dir.mkdir()
        notes_dir = project_dir / 'notes'
        notes_dir.mkdir()

        config_file = project_dir / 'config.toml'
        config_file.write_text(
            textwrap.dedent("""
            base = "."
            [[input]]
            name = "requirements"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]

            [[input]]
            name = "notes"
            dir = "notes"
            driver = "obsidian"
            atype = "NOTE"
            marker = "NOTE"
            markers = ["COM"]
        """).strip(),
            encoding='utf-8',
        )

        (docs_dir / 'test.md').write_text('[COM]in docs[/COM]', encoding='utf-8')
        (notes_dir / 'test.md').write_text('[COM]in notes[/COM]', encoding='utf-8')

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config, section='requirements')

        docs_content = (docs_dir / 'test.md').read_text(encoding='utf-8')
        notes_content = (notes_dir / 'test.md').read_text(encoding='utf-8')

        assert '[COM 1]in docs[/COM]' in docs_content
        assert notes_content == '[COM]in notes[/COM]'  # untouched


class TestMarkerFilter:
    """Test --marker filtering."""

    def test_marker_filter_only_targets_specific_type(self, params, tmp_path):
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM", "NOTE"]
        """,
            {
                'test.md': '[COM]a comment[/COM]\n[NOTE]a note[/NOTE]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config, marker_filter='COM')

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM 1]a comment[/COM]' in content
        assert '[NOTE]a note[/NOTE]' in content  # NOT renumbered


class TestReExtraction:
    """Verify that re-extraction after renumbering produces explicit IDs."""

    def test_re_extract_after_renumber(self, params, tmp_path):
        """After renumbering, re-extraction shows explicit_id=True for all blocks."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM", "NOTE"]
        """,
            {
                'test.md': '[COM]comment one[/COM]\n[NOTE]note one[/NOTE]\n[COM]comment two[/COM]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        # Re-extract
        config2 = Config(params=params, config_filename=config_file)
        record = config2.input_records()[0]
        extractor = EXTRACTORS[record.driver](config2, record, config2.metamodel)
        blocks = extractor.extract_blocks_from_file(project_dir / 'docs' / 'test.md')

        marked_blocks = [b for b in blocks if isinstance(b, TextBlock) and b.marker is not None]
        assert len(marked_blocks) == 3
        for b in marked_blocks:
            assert b.explicit_id is True
            assert b.id is not None


class TestLineEndingsPreservation:
    """Verify original line endings are preserved on write."""

    def test_crlf_preserved(self, params, tmp_path):
        """CRLF in source gets preserved on write."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM]comment[/COM]\r\nsome other line\r\n',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        filepath = project_dir / 'docs' / 'test.md'
        raw = filepath.read_bytes()
        assert b'\r\n' in raw
        assert b'[COM 1]comment[/COM]\r\n' in raw


class TestMultipleFiles:
    """Test renumbering across multiple files shares ID space per marker type."""

    def test_ids_shared_across_files(self, params, tmp_path):
        """IDs continue from max across all files in a section."""
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'a.md': '[COM 2]existing[/COM]',
                'b.md': '[COM]first new[/COM]',
                'c.md': '[COM]second new[/COM]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        a_content = (project_dir / 'docs' / 'a.md').read_text(encoding='utf-8')
        b_content = (project_dir / 'docs' / 'b.md').read_text(encoding='utf-8')
        c_content = (project_dir / 'docs' / 'c.md').read_text(encoding='utf-8')

        assert '[COM 2]existing[/COM]' in a_content
        assert '[COM 3]first new[/COM]' in b_content
        assert '[COM 4]second new[/COM]' in c_content


class TestLeadingZeros:
    """Test that existing IDs with leading zeros are parsed correctly."""

    def test_leading_zeros_contribute_to_max(self, params, tmp_path):
        project_dir, config_file = _make_project(
            tmp_path,
            """
            base = "."
            [[input]]
            name = "test"
            dir = "docs"
            driver = "obsidian"
            atype = "SYS"
            marker = "SYS"
            markers = ["COM"]
        """,
            {
                'test.md': '[COM 005]padded[/COM]\n[COM]new[/COM]',
            },
        )

        config = Config(params=params, config_filename=config_file)
        renumber_markers(config)

        content = (project_dir / 'docs' / 'test.md').read_text(encoding='utf-8')
        assert '[COM 005]padded[/COM]' in content
        assert '[COM 6]new[/COM]' in content  # 005 parsed as 5, next is 6
